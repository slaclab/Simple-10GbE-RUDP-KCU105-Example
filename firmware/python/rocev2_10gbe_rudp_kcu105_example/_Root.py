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
            rocev2Cfg,            # RoCEv2ServerCfg (required): host-NIC config (D-11)
            ip          = '192.168.2.10',  # FPGA IP address (RUDP transport)
            zmqSrvPort  = 9099,   # Set to zero if dynamic (instead of static)
            useDcqcn    = True,   # Enable DCQCN congestion control in the Core
            transportCfg = None,  # RoCEv2TransportCfg: transport/QP-tuning knobs (D-12)
            **kwargs):
        super().__init__(timeout=5.0, **kwargs)

        # Single transport/QP-tuning cfg forwarded into BOTH engine.setupConnection()
        # and server.completeConnection() so the FPGA and host sides cannot drift (D-02/D-12).
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
            width        = 128,
            checkPayload = True,
            expand       = True,
        )
        self.add(self.prbsRx)
        self.rdmaRx.stream >> self.prbsRx

        #################################################################

    def start(self, **kwargs):
        super().start(**kwargs)

        # Bring-up hand-off (D-03/D-04): super().start() has already brought up the
        # RUDP/SRP transport and run the server's host-side _start(), so the metadata
        # bus is reachable. Run the host↔FPGA hand-off, forwarding the single
        # transportCfg into BOTH the engine and the server so they cannot drift.
        # A failure here propagates and pyrogue unwinds into stop() (D-05).
        cfg = self._transportCfg
        params = self.rdmaRx.getHostParams()
        fpga = self.Core.RoCEv2Engine.setupConnection(
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

        # Point the FW UDP engine at the host NIC (RoCEv2 UDP port 4791).
        hostIp = self.rdmaRx.HostIp.get()
        self.Core.UdpEngine.ClientRemotePort[0].set(4791)
        self.Core.UdpEngine.ClientRemoteIp[0].set(hostIp)
        self.rdmaRx.printConnInfo()

    def stop(self) -> None:
        """Tear down the FPGA QP before transport is stopped (D-08)."""
        # Disarm the RDMA-engine dispatcher first, else the FPGA floods a destroyed QP.
        # This is the engine-level gate (not the application stream), so it is disarmed
        # regardless of streaming state to protect clean teardown.
        try:
            self.Core.RoCEv2Engine.Rdma.DispatchEnable.set(False)
            time.sleep(0.1)  # let the in-flight WRITE drain before QP teardown
        except AttributeError:
            pass
        # Tear down the FPGA QP before super().stop() — needs the RUDP transport still
        # up so the metadata bus works. Safe no-op when no connection was established.
        self.Core.RoCEv2Engine.teardownConnection()
        super().stop()
