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

rogue.Version.minVersion('6.14.1')

# Path MTU is fixed at 4096 bytes (libibverbs ibv_mtu enum value 5).
IBV_MTU_4096 = 5

class Root(pr.Root):
    def __init__(self,
            ip          = '192.168.2.10',
            zmqSrvPort  = 9099,   # Set to zero if dynamic (instead of static)
            # ----------------------------------------------------------------
            # RoCEv2 options (meta mode only)
            # ----------------------------------------------------------------
            useDcqcn        = True,
            roceDevice      = 'rxe0',       # ibverbs device name (rxe0=softRoCE, mlx5_0=HW NIC)
            roceIbPort      = 1,            # ibverbs port number
            roceGidIndex    = -1,           # GID index (-1 = auto-detect from ip)
            roceMaxPay      = None,         # Max payload bytes per RDMA SEND (None = 9000)
            roceQDepth      = None,         # RX queue depth (None = 256)
            roceOffset      = 0x0000_0000,  # AXI-lite byte offset of RoCEv2 engine registers
            roceMinRnrTimer = 12,           # IB min_rnr_timer code (12=0.64ms, 1=0.01ms, 31=491ms).
                                            # Native FW<->NIC flow-control knob: how long the FPGA
                                            # requester backs off after an RNR NAK (empty host RQ)
                                            # before retrying the SEND. Small enough for throughput,
                                            # large enough to avoid an RNR-NAK storm. Sweep 8..16.
            roceRnrRetry    = 7,            # FPGA RNR retry count (7=infinite — never fault on RNR)
            roceRetryCount  = 3,            # FPGA retry count for non-RNR errors
            **kwargs):
        super().__init__(timeout=5.0, **kwargs)

        #################################################################

        self.zmqServer = pyrogue.interfaces.ZmqServer(root=self, addr='127.0.0.1', port=zmqSrvPort)
        self.addInterface(self.zmqServer)

        #################################################################

        # UDP/RSSI clients — both always present
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

        # RoCEv2Server resolves its own defaults (maxPayload/rxQueueDepth None
        # -> C++ Default*, gidIndex -1 -> auto-detect from ip) and logs the
        # streaming configuration, so pass the raw options straight through.
        self._rdmaRx = self.add(pr.protocols.RoCEv2Server(
            name             = 'rdmaRx',
            ip               = ip,
            deviceName       = roceDevice,
            ibPort           = roceIbPort,
            gidIndex         = roceGidIndex,
            maxPayload       = roceMaxPay,
            rxQueueDepth     = roceQDepth,
            pmtu             = IBV_MTU_4096,
            minRnrTimer      = roceMinRnrTimer,
            rnrRetry         = roceRnrRetry,
            retryCount       = roceRetryCount,
            roceEngineOffset = roceOffset,
            roceMemBase      = self.srp,
            roceEngine       = self.Core.RoCEv2Engine,
            expand           = False,
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

    def start(self, **kwargs):
        super().start(**kwargs)

        # Validate the RoCEv2 RC connection came up (RoCEv2Server._start drives
        # the FPGA QP to RTS). Raise here so the caller's `with Root(...)` block
        # unwinds into stop() for a clean teardown instead of leaving a
        # half-connected engine.
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
        # Disarm the PRBS source + RDMA dispatcher BEFORE tearing down the QP.
        # Otherwise the FPGA is left free-running RDMA WRITEs at a destroyed QP,
        # flooding the link and wedging the App datapath until an FPGA reload —
        # the 0xF50 softRst only resets the Core transport, not the App. This
        # leaked TxEn/DispatchEnable is what makes a software reconnect fail
        # (rxCount stays 0) after the GUI/stream path leaves the source armed.
        try:
            self.App.SsiPrbsTx.TxEn.set(False)
            self.App.RoCEv2AxiStreamRdma.DispatchEnable.set(False)
            time.sleep(0.1)  # let the in-flight WRITE drain before QP teardown
        except AttributeError:
            pass
        # Tear down the FPGA QP here, BEFORE super().stop(). The metadata-bus
        # teardown drives SendMetaData over SRP-over-RUDP, so it must run while
        # the RUDP transport is still alive. super().stop() -> Device._stop()
        # tears down sibling interfaces/protocols (the RUDP transport) before it
        # ever recurses into rdmaRx._stop(), so relying on that traversal to
        # tear down the QP races the transport shutdown and the SendMetaData
        # write times out. teardownFpgaQp() is idempotent, so rdmaRx._stop()
        # safely no-ops on the now-zero FPGA QPN.
        if hasattr(self.rdmaRx, 'teardownFpgaQp'):
            self.rdmaRx.teardownFpgaQp()
        super().stop()
