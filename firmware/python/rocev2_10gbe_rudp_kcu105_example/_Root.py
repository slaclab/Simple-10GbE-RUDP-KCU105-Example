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
            ip          = '192.168.2.10',  # FPGA IP address (RUDP transport + default cfg seed)
            zmqSrvPort  = 9099,   # Set to zero if dynamic (instead of static)
            useDcqcn    = True,   # Enable DCQCN congestion control in the Core
            rocev2Cfg   = None,   # RoCEv2ServerCfg; None = default fixed-4096 cfg targeting `ip`
            **kwargs):
        super().__init__(timeout=5.0, **kwargs)

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
            rocev2Engine = self.Core.RoCEv2Engine,
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

        # Fail fast (and unwind into stop()) if the RC connection did not reach RTS.
        state = self.rdmaRx.ConnectionState.get()
        if state != 'Connected':
            raise rogue.GeneralError('Root.start', f"RoCEv2 not connected (state={state})")

        appTx = self.find(typ=baseBoard.AppTx)
        for devPtr in appTx:
            devPtr.ContinuousMode.set(False)

        try:
            self.App.SsiPrbsTx.TxEn.set(False)
            self.App.RoCEv2AxiStreamRdma.DispatchEnable.set(False)
        except AttributeError:
            pass
        self.CountReset()

    def stop(self) -> None:
        """Tear down FPGA QP before transport is stopped."""
        # Disarm PRBS source + RDMA dispatcher first, else the FPGA floods a destroyed QP.
        try:
            self.App.SsiPrbsTx.TxEn.set(False)
            self.App.RoCEv2AxiStreamRdma.DispatchEnable.set(False)
            time.sleep(0.1)  # let the in-flight WRITE drain before QP teardown
        except AttributeError:
            pass
        # Tear down the FPGA QP before super().stop() — needs the RUDP transport still up.
        if hasattr(self.rdmaRx, 'teardownFpgaQp'):
            self.rdmaRx.teardownFpgaQp()
        super().stop()
