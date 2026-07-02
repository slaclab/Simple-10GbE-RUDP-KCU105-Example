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
import rogue.protocols.packetizer
import rogue.utilities.fileio

import simple_10gbe_rudp_kcu105_example as baseBoard
import rocev2_10gbe_rudp_kcu105_example as roceBoard

rogue.Version.minVersion('6.15.0')

class Root(pr.Root):
    def __init__(self,
            rocev2Cfg,            # RoCEv2ServerCfg (required): host-NIC config
            ip          = '192.168.2.10',  # FPGA IP address (RUDP transport)
            zmqSrvPort  = 9099,   # Set to zero if dynamic (instead of static)
            useDcqcn    = True,   # Enable DCQCN congestion control in the Core
            transportCfg = None,  # RoCEv2TransportCfg: transport/QP-tuning knobs
            p2p         = True,   # Default to switchless point-to-point bring-up (Not-ECT, DCQCN bypassed)
            dscp        = 26,     # Managed-fabric only (p2p=False): IP-header DSCP (26 = AF31)
            ecn         = 2,      # Managed-fabric only (p2p=False): IP-header ECN (2 = ECT(0) = b"10")
            enableDcqcn = True,   # Managed-fabric only (p2p=False): run FW DCQCN (False bypasses it)
            **kwargs):
        super().__init__(timeout=5.0, **kwargs)

        # Bring-up posture: p2p drives the egress ECN/DSCP and DCQCN-bypass setup
        # in start(). The dscp/ecn/enableDcqcn knobs only apply when p2p is False.
        self._p2p         = p2p
        self._dscp        = dscp
        self._ecn         = ecn
        self._enableDcqcn = enableDcqcn

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

        # Strip the FW AxiStreamPacketizer2 framing before the PRBS check.
        # CoreV2(ibCRC=False, obCRC=False, enSsi=True): no inbound CRC (FW
        # CRC_MODE_G="NONE"), SSI SOF/EOF enabled. FW emits OUTPUT_TDEST_G=0, so the
        # depacketized payload exits on application(0).
        self._depack = rogue.protocols.packetizer.CoreV2(False, False, True)
        self.rdmaRx.stream          >> self._depack.transport()
        self._depack.application(0) >> self.prbsRx

        #################################################################

    def start(self, **kwargs):
        super().start(**kwargs)

        # pr.Root.__enter__ calls start() directly and __exit__/stop() only runs if
        # __enter__ returns, so an exception in the hand-off would skip teardown and
        # leak the transport/poll threads or a half-established QP. Unwind through
        # stop() before re-raising; teardownConnection() is best-effort with no live
        # QP, and stop() SoftResets the engine to clear any partial QP/PSN state.
        try:
            self._handoff()
        except Exception:
            self.stop()
            raise

    def _handoff(self):
        # Host<->FPGA hand-off. super().start() already brought up the RUDP/SRP
        # transport and the server's host-side _start(), so the metadata bus is
        # reachable. Forward the single transportCfg into BOTH the engine and the
        # server so the two sides stay in sync.
        cfg = self._transportCfg

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

        # Point the FW UDP engine at the host NIC. Ordering vs the hand-off above
        # is free: that runs over the SRP register bus (port 8192), while the 4791
        # RoCEv2 datapath only carries traffic once DispatchEnable is armed later.
        hostIp = self.rdmaRx.HostIp.get()
        self.Core.UdpEngine.ClientRemotePort[0].set(4791)
        self.Core.UdpEngine.ClientRemoteIp[0].set(hostIp)

        # Configure egress ECN/DSCP and DCQCN posture for the deployment.
        #
        # p2p (default): switchless link. Force Not-ECT, no DSCP marking, and
        # bypass DCQCN. The FW reset default is already Not-ECT/DSCP=0 (Rudp.vhd
        # U_UDP); set it explicitly so the posture holds regardless of prior
        # runtime state. ECT(0) would opt the flow into the host NIC's hardware
        # DCQCN: with no ECN-marking fabric here, throttle-induced microbursts get
        # CE-marked, the NIC returns CNPs, and the FW throttle self-sustains (CNPs
        # reset the rate-increase timer faster than it fires) — throughput
        # collapses until a source drain. Not-ECT removes that spurious trigger.
        #
        # Managed fabric (p2p=False): apply the configured DSCP/ECN to join the
        # switch lossless/ECN traffic class, leaving DCQCN active unless
        # enableDcqcn was cleared.
        if self._p2p:
            self.Core.UdpEngine.EcnFlag.set(0)  # 0 = Not-ECT
            self.Core.UdpEngine.Dscp.set(0)
        else:
            self.Core.UdpEngine.EcnFlag.set(self._ecn)
            self.Core.UdpEngine.Dscp.set(self._dscp)

        # DcqcnBypass: bypass FW DCQCN for p2p, or for an explicit enableDcqcn=False on a
        # fabric. RNR backoff is independent — set via transportCfg at setupConnection above.
        self.setP2pMode(self._p2p or not self._enableDcqcn)

        self.rdmaRx.printConnInfo()


    def setP2pMode(self, enable):
        """Point-to-point bring-up toggle for FW DCQCN.

        Toggles the live AXI-Lite register Core.RoCEv2AxiStreamRdma.Dcqcn.DcqcnBypass
        so the bypass takes effect immediately (True = gate CNP + clamp Rc/Rt to line
        rate).

        RNR backoff is deliberately NOT set here: min_rnr_timer is host-NIC QP state
        fixed at QP setup and is owned solely by self._transportCfg.minRnrTimer, which
        start() forwards into setupConnection()/completeConnection(). Decoupling the RNR
        timer from the DCQCN-bypass toggle lets a slow (softRoCE) responder keep a larger
        backoff while still bypassing DCQCN on a switchless link — forcing the minimal
        0.01ms backoff here storms RNR-NAKs on a software responder.
        """
        self.Core.RoCEv2AxiStreamRdma.Dcqcn.DcqcnBypass.set(enable)

    def stop(self) -> None:
        """Tear down the FPGA QP before transport is stopped."""
        # Must run before super().stop(): pr.Root.stop() -> Device._stop() recurses in
        # ADD order, and self.rudp[0] was added before Core, so the transport tears
        # down first. An Engine._stop() hook would then fire after the metadata bus is
        # already dead (register timeout — verified on hardware). So disarm the
        # dispatcher and tear down the QP here, while the transport is still up.
        # Guarded so a missing node (or any teardown error) never aborts stop() —
        # super().stop() must always run to release the transport/poll threads.
        try:
            self.Core.RoCEv2AxiStreamRdma.Core.DispatchEnable.set(False)
            time.sleep(0.1)  # let the in-flight SEND drain before QP teardown
            self.Core.RoCEv2AxiStreamRdma.Engine.teardownConnection()
            # Force the FW RoceConfigurator back to IDLE. It has no response timeout, so
            # an out-of-order / unexpected-state DESTROY can wedge it in GET_RESPONSE_S
            # (the multi-second "DESTROY QP/MR/PD timeout"); a SoftReset pulse clears that
            # and any stale QP/PSN state so the next bring-up starts clean.
            self.Core.RoCEv2AxiStreamRdma.Engine.SoftReset()
        except Exception as e:
            print(f"Root.stop: RoCEv2 teardown skipped/failed ({e}); "
                  f"proceeding to transport stop.")
        finally:
            super().stop()
