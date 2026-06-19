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

# IBV_MTU enum values — mirrors libibverbs ibv_mtu
IBV_MTU_256  = 1
IBV_MTU_512  = 2
IBV_MTU_1024 = 3
IBV_MTU_2048 = 4
IBV_MTU_4096 = 5

_MTU_BYTES = {1: 256, 2: 512, 3: 1024, 4: 2048, 5: 4096}

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
            rocePmtu        = IBV_MTU_4096, # Path MTU: IBV_MTU_256/512/1024/2048/4096
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
        self.rudp = [None for i in range(2)]
        for i in range(2):
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

        # Streaming path — RUDP[1] always connected as upstream
        self.stream = self.rudp[1].application(0)

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

        # Resolve RoCEv2 defaults
        import rogue.protocols.rocev2 as _rv2
        _maxPay   = roceMaxPay   if roceMaxPay   is not None else _rv2.DefaultMaxPayload
        _qDepth   = roceQDepth   if roceQDepth   is not None else _rv2.DefaultRxQueueDepth
        _gidIndex = roceGidIndex if roceGidIndex >= 0 else self._autoGidIndex(roceDevice, ip)
        _mtu_b    = _MTU_BYTES.get(rocePmtu, '?')
        self._log.info(
            f"RoCEv2 streaming enabled: device={roceDevice}  "
            f"gidIndex={_gidIndex}  pmtu={_mtu_b} bytes  "
            f"maxPayload={_maxPay}  queueDepth={_qDepth}"
        )

        self._rdmaRx = self.add(pr.protocols.RoCEv2Server(
            name             = 'rdmaRx',
            ip               = ip,
            deviceName       = roceDevice,
            ibPort           = roceIbPort,
            gidIndex         = _gidIndex,
            maxPayload       = _maxPay,
            rxQueueDepth     = _qDepth,
            pmtu             = rocePmtu,
            minRnrTimer      = roceMinRnrTimer,
            rnrRetry         = roceRnrRetry,
            retryCount       = roceRetryCount,
            roceEngineOffset = roceOffset,
            roceMemBase      = self.srp,
            roceEngine       = self.Core.RoCEv2Engine,
            expand           = False,
        ))

        # rdmaRx.stream is the RDMA receive endpoint;
        # self.stream remains the RUDP streaming endpoint
        self.rdmaStream = self.rdmaRx.stream

        # Host-side PRBS data-integrity check on the RDMA receive stream.
        self.prbsRx = pr.utilities.prbs.PrbsRx(
            name         = 'PrbsRx',
            width        = 128,
            checkPayload = True,
            expand       = True,
        )
        self.add(self.prbsRx)
        self.rdmaStream >> self.prbsRx

    def start(self, **kwargs):
        super().start(**kwargs)
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
        if hasattr(self.rdmaRx, 'teardownFpgaQp'):
            self.rdmaRx.teardownFpgaQp()
        super().stop()

    @staticmethod
    def _autoGidIndex(device: str, ip: str) -> int:
        """Find the GID index matching ip on the given ibverbs device."""
        import subprocess
        try:
            out = subprocess.check_output(
                ['ibv_devinfo', '-v', '-d', device],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            for line in out.splitlines():
                line = line.strip()
                if 'GID[' in line and ip in line:
                    return int(line.split('[')[1].split(']')[0])
        except Exception:
            pass
        return 1  # safe default for softRoCE
