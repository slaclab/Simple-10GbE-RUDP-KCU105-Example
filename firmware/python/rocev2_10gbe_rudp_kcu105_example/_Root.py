#-----------------------------------------------------------------------------
# This file is part of the 'Simple-10GbE-RUDP-KCU105-Example'. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the 'Simple-10GbE-RUDP-KCU105-Example', including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------

import time

import pyrogue  as pr
import pyrogue.protocols
import pyrogue.utilities.fileio
import pyrogue.utilities.prbs
import pyrogue.interfaces.simulation

import rogue
import rogue.hardware.axi
import rogue.interfaces.stream
import rogue.utilities.fileio

import simple_10gbe_rudp_kcu105_example as baseBoard
import rocev2_10gbe_rudp_kcu105_example as roceBoard

# Currently using rogue@rocev2-soft-reset-on-reconnect branch
#rogue.Version.minVersion('6.15.0')

class Root(pr.Root):
    def __init__(self,
            rocev2Cfg,            # RoCEv2ServerCfg (required): host-NIC config
            ip          = '192.168.2.10',  # FPGA IP address (RUDP transport)
            zmqSrvPort  = 9099,   # Set to zero if dynamic (instead of static)
            useDcqcn    = True,   # Enable DCQCN congestion control in the Core
            transportCfg = None,  # RoCEv2TransportCfg: transport/QP-tuning knobs
            **kwargs):
        super().__init__(timeout=5.0, **kwargs)

        # Single transport/QP-tuning cfg forwarded into BOTH engine.setupConnection()
        # and server.completeConnection() so the FPGA and host sides cannot drift.
        self._transportCfg = transportCfg if transportCfg is not None else pr.protocols.RoCEv2TransportCfg()

        #################################################################

        self.zmqServer = pyrogue.interfaces.ZmqServer(root=self, addr='127.0.0.1', port=zmqSrvPort)
        self.addInterface(self.zmqServer)

        #################################################################

        # UDP/RSSI client
        self.rudp = [None for i in range(1)]
        for i in range(1):
            self.rudp[i] = pr.protocols.UdpRssiPack(
                name    = f'SwRudpClient[{i}]',
                host    = ip,
                port    = 8192 + i,
                packVer = 2,
                jumbo   = (i > 0),
                expand  = False,
            )
            self.add(self.rudp[i])

        # SRPv3 for register access
        self.srp = rogue.protocols.srp.SrpV3()
        self.srp == self.rudp[0].application(0)

        #################################################################

        # ---- RoCEv2 receive channel (additive, alongside RUDP) ----
        self.add(baseBoard.Core(
            offset   = 0x0000_0000,
            memBase  = self.srp,
            rocev2   = True,
            dcqcn    = useDcqcn,
            expand   = False,
        ))

        self.add(roceBoard.App(
            offset   = 0x8000_0000,
            memBase  = self.srp,
            expand   = True,
        ))

        #################################################################

        # RoCEv2 receive server (resolves cfg sentinels + auto-detects GID internally).
        self._rdmaRx = self.add(pr.protocols.RoCEv2Server(
            name         = 'rdmaRx',
            rocev2Cfg    = rocev2Cfg,
            expand       = False,
        ))

        # Host-side PRBS data-integrity check on the RDMA receive stream.
        self.prbsRx = pr.utilities.prbs.PrbsRx(
            name         = 'PrbsRx',
            width        = 64,
            checkPayload = True,
            expand       = True,
        )
        self.add(self.prbsRx)
        self.rdmaRx.stream >> self.prbsRx

        #################################################################

    def start(self, **kwargs):
        super().start(**kwargs)

        # Bring-up hand-off: super().start() has already brought up the
        # RUDP/SRP transport and run the server's host-side _start(), so the metadata
        # bus is reachable. Run the host↔FPGA hand-off, forwarding the single
        # transportCfg into BOTH the engine and the server so they stay in sync.
        #
        # A failure mid-hand-off must NOT leak the started transport/poll
        # threads or a partially-established FPGA QP. pr.Root.__enter__ calls
        # start() directly, and Python only invokes __exit__/stop() if __enter__
        # RETURNS — so an exception here would otherwise skip teardown entirely.
        # Wrap the hand-off and unwind through stop() ourselves before re-raising.
        # teardownConnection() is a safe no-op when no FPGA QP is live, so this is
        # correct whether the failure was early (no QP yet) or late (QP up).
        cfg = self._transportCfg
        try:
            params = self.rdmaRx.getHostParams()
            fpga = self.Core.RoCEv2AxiStreamRdma.Engine.setupConnection(
                **params._asdict(),
                pmtu        = cfg.pmtu,
                minRnrTimer = cfg.minRnrTimer,
                rnrRetry    = cfg.rnrRetry,
                retryCount  = cfg.retryCount,
            )
            self.rdmaRx.completeConnection(
                fpga.fpgaQpn,
                fpgaLkey    = fpga.lkey,
                pmtu        = cfg.pmtu,
                minRnrTimer = cfg.minRnrTimer,
                rnrRetry    = cfg.rnrRetry,
                retryCount  = cfg.retryCount,
            )

            # Point the FW UDP engine at the host NIC. Ordering is free: the QP
            # hand-off above runs over the SRP register bus (port 8192), not this
            # RoCEv2 UDP client (port 4791), and the 4791 datapath only carries
            # traffic once DispatchEnable is armed (later, by the test/GUI) — so
            # this can sit before or after the hand-off with no functional effect.
            hostIp = self.rdmaRx.HostIp.get()
            self.Core.UdpEngine.ClientRemotePort[0].set(4791)
            self.Core.UdpEngine.ClientRemoteIp[0].set(hostIp)

            # Mark egress Not-ECT on this switchless point-to-point link. The FW
            # default is ECT(0) (ECN_G="10"), which opts the flow into the host
            # NIC's hardware DCQCN: under throttle-induced microbursts the NIC
            # CE-marks + returns CNPs, the FW DCQCN throttles, and the loop is
            # self-sustaining (CNPs reset the rate-increase timer faster than it
            # can fire) — so throughput collapses and only recovers on a source
            # drain. There is no ECN-marking fabric here, so Not-ECT removes the
            # spurious trigger entirely. Set EcnFlag back to ECT(0) (2) at runtime
            # if this design is ever deployed behind a real ECN/DCQCN fabric.
            try:
                self.Core.UdpEngine.EcnFlag.set(0)  # 0 = Not-ECT
            except AttributeError:
                pass

            self.rdmaRx.printConnInfo()
        except Exception:
            self.stop()
            raise

    def setP2pMode(self, enable):
        """Point-to-point bring-up toggle.

        Couples the two halves of the P2P fix:

        1. Toggles the LIVE AXI-Lite register Core.RoCEv2AxiStreamRdma.Dcqcn.DcqcnBypass
           — this is a live FPGA register, so the DCQCN bypass takes effect
           immediately. Guarded so a missing engine node (ip='sim'/'emu' or
           ROCEV2 disabled) degrades gracefully instead of aborting.
        2. Records the intended RNR backoff code for the NEXT bring-up by writing
           into self._transportCfg.minRnrTimer — the field start() forwards into
           setupConnection()/completeConnection(). RNR is host-NIC QP state fixed
           at QP setup, so this does NOT live-reconfigure the QP; the minimal
           backoff (code 1) only re-applies on the next reconnect/restart.
        """
        try:
            self.Core.RoCEv2AxiStreamRdma.Dcqcn.DcqcnBypass.set(enable)
        except AttributeError:
            pass

        if enable:
            # Record minimal RNR backoff (code 1) for the next bring-up; start()
            # reads self._transportCfg.minRnrTimer into setupConnection()/
            # completeConnection(). No live QP reconfig here.
            self._transportCfg.minRnrTimer = 1
            print(
                "setP2pMode: DcqcnBypass toggled LIVE; minRnrTimer=1 recorded — "
                "RNR backoff takes effect on the NEXT reconnect/restart.",
            )

    def stop(self) -> None:
        """Tear down the FPGA QP before transport is stopped."""
        # The teardown MUST run here, before super().stop(): pr.Root.stop() ->
        # Device._stop() recurses through child devices in ADD order, and the RUDP
        # transport (self.rudp[0]) was added before Core, so it is torn down first.
        # A RoCEv2AxiStreamRdma.Engine._stop() hook would therefore fire AFTER the metadata bus is
        # already dead (register timeout) — verified on hardware. So disarm the
        # dispatcher and tear down the QP explicitly while the transport is still up.
        # Guarded so a missing Core.RoCEv2Engine node (or any teardown error) never
        # aborts stop() before super().stop() runs.
        try:
            self.Core.RoCEv2AxiStreamRdma.Core.DispatchEnable.set(False)
            time.sleep(0.1)  # let the in-flight WRITE drain before QP teardown
            self.Core.RoCEv2AxiStreamRdma.Engine.teardownConnection()
        except AttributeError:
            pass
        super().stop()
