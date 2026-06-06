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
import pyrogue.interfaces.simulation

import rogue
import rogue.hardware.axi
import rogue.interfaces.stream
import rogue.utilities.fileio

import simple_10gbe_rudp_kcu105_example as baseBoard
import rocev2_10gbe_rudp_kcu105_example as roceBoard

# TODO: Uncomment this after the rogue v6.14.0 tag release
#rogue.Version.minVersion('6.14.0')

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
            promProg    = False,  # Flag to disable all devices not related to PROM programming
            enSwRx      = True,   # Flag to enable the software stream receiver
            xvcSrvEn    = True,   # Flag to include the XVC server
            zmqSrvPort  = 9099,   # Set to zero if dynamic (instead of static)
            # ----------------------------------------------------------------
            # RoCEv2 options (meta mode only)
            # ----------------------------------------------------------------
            useRoce         = False,        # Add RoCEv2 RDMA receive channel alongside UDP/RSSI
            useDcqcn        = True,
            roceDevice      = 'rxe0',       # ibverbs device name (rxe0=softRoCE, mlx5_0=HW NIC)
            roceIbPort      = 1,            # ibverbs port number
            roceGidIndex    = -1,           # GID index (-1 = auto-detect from ip)
            roceMaxPay      = None,         # Max payload bytes per RDMA WRITE (None = 9000)
            roceQDepth      = None,         # RX queue depth (None = 256)
            rocePmtu        = IBV_MTU_4096, # Path MTU: IBV_MTU_256/512/1024/2048/4096
            roceOffset      = 0x0000_0000,  # AXI-lite byte offset of RoCEv2 engine registers
            roceMinRnrTimer = 1,            # IB min_rnr_timer (1=0.01ms, 31=491ms)
            roceRnrRetry    = 7,            # FPGA RNR retry count (7=infinite)
            roceRetryCount  = 3,            # FPGA retry count for non-RNR errors
            **kwargs):
        super().__init__(timeout=(5.0 if (ip != 'sim') else 100.0), **kwargs)

        #################################################################

        self.zmqServer = pyrogue.interfaces.ZmqServer(root=self, addr='127.0.0.1', port=zmqSrvPort)
        self.addInterface(self.zmqServer)

        #################################################################

        self.enSwRx   = not promProg and enSwRx
        self.promProg = promProg
        self.sim      = (ip == 'sim')
        self.useRoce  = useRoce and not promProg and not self.sim
        self.useDcqcn = useDcqcn and not promProg and not self.sim

        # Resolve RoCEv2 defaults
        if self.useRoce:
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

        #################################################################
        # Transport / memory path  (unchanged from upstream)
        #################################################################

        if ip == 'emu':
            self.srp    = pr.interfaces.simulation.MemEmulate()
            self.stream = rogue.interfaces.stream.Master()

        elif ip == 'sim':
            self._pollEn   = False
            self._initRead = False
            self.srp    = rogue.interfaces.memory.TcpClient('localhost', 10000)
            self.stream = rogue.interfaces.stream.TcpClient('localhost', 10002)

        else:
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
            if self.useRoce:
                # Core must be added first so we can reference Core.RoCEv2Engine.
                # We add it here early; the block below skips re-adding it.
                self.add(baseBoard.Core(
                    offset   = 0x0000_0000,
                    memBase  = self.srp,
                    sim      = self.sim,
                    promProg = promProg,
                    rocev2   = self.useRoce,
                    dcqcn    = self.useDcqcn,
                    expand   = True,
                ))
                self._coreAlreadyAdded = True

                _rdmaRx = pr.protocols.RoCEv2Server(
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
                )
                self.add(_rdmaRx)
                # rdmaRx.stream is the RDMA receive endpoint;
                # self.stream remains the RUDP streaming endpoint
                self.rdmaStream = self.rdmaRx.stream

            # XVC server (unchanged from upstream)
            if not self.promProg and xvcSrvEn:
                self.udpClient = rogue.protocols.udp.Client(ip, 2542, False)
                self.xvc       = rogue.protocols.xilinx.Xvc(2542)
                self.addProtocol(self.xvc)
                self.udpClient == self.xvc

        #################################################################
        # Software receiver and file writer (unchanged from upstream)
        #################################################################

        if self.enSwRx:
            self.dataWriter = pr.utilities.fileio.StreamWriter()
            self.add(self.dataWriter)

            self.swRx = baseBoard.SwRx(expand=True)
            self.add(self.swRx)

            self.stream >> self.swRx
            self.stream >> self.dataWriter.getChannel(0)

            # If RoCEv2 is enabled, also write RDMA frames to a separate channel
            if self.useRoce:
                self.rdmaStream >> self.dataWriter.getChannel(1)

        #################################################################
        # Devices (Core added early above if useRoce, otherwise add here)
        #################################################################

        if not getattr(self, '_coreAlreadyAdded', False):
            self.add(baseBoard.Core(
                offset   = 0x0000_0000,
                memBase  = self.srp,
                sim      = self.sim,
                promProg = promProg,
                expand   = True,
            ))

        if not promProg:
            self.add(roceBoard.App(
                offset   = 0x8000_0000,
                memBase  = self.srp,
                sim      = self.sim,
                expand   = True,
            ))

    def start(self, **kwargs):
        super().start(**kwargs)
        if not self.sim:
            appTx = self.find(typ=baseBoard.AppTx)
            for devPtr in appTx:
                devPtr.ContinuousMode.set(False)
            self.CountReset()

    def _start(self) -> None:
        """
        Wait for SRP/RSSI link before starting RoCEv2 connection sequence.
        """
        if self.useRoce and hasattr(self, 'rudp'):
            self._log.info("Waiting for SRP/RSSI link before RoCEv2 setup...")
            deadline = time.monotonic() + 30.0
            while not self.rudp[0]._rssi.getOpen():
                if time.monotonic() > deadline:
                    raise RuntimeError(
                        "Timeout waiting for SRP/RSSI link to come up")
                time.sleep(0.1)
            self._log.info("SRP/RSSI link is up — proceeding with RoCEv2 setup")
            time.sleep(0.5)
        super()._start()

    def stop(self) -> None:
        """Tear down FPGA QP before transport is stopped."""
        if self.useRoce and hasattr(self, 'rdmaRx') and hasattr(self.rdmaRx, 'teardownFpgaQp'):
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
