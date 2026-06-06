import setupLibPaths
import argparse
import pyrogue as pr
import pyrogue.pydm
import logging
import simple_10gbe_rudp_kcu105_example as devBoard

# IBV_MTU constants for the --rocePmtu argument
IBV_MTU_256  = 1
IBV_MTU_512  = 2
IBV_MTU_1024 = 3
IBV_MTU_2048 = 4
IBV_MTU_4096 = 5

if __name__ == "__main__":

    # Convert str to bool
    argBool = lambda s: s.lower() in ['true', 't', 'yes', '1']

    # Set the argument parser
    parser = argparse.ArgumentParser()

    # -------------------------------------------------------------------------
    # Original arguments (unchanged)
    # -------------------------------------------------------------------------
    parser.add_argument(
        "--ip",
        type     = str,
        required = False,
        default  = '192.168.2.10',
        help     = "IP address",
    )
    parser.add_argument(
        "--pollEn",
        type     = argBool,
        required = False,
        default  = True,
        help     = "Enable auto-polling",
    )
    parser.add_argument(
        "--initRead",
        type     = argBool,
        required = False,
        default  = True,
        help     = "Enable read all variables at start",
    )
    parser.add_argument(
        "--LmkRegFile",
        type     = str,
        required = False,
        default  = "../configurations/LmkForCtaJMode7.txt",
        help     = "Path to the LMK04828 register .txt file from TICS-PRO",
    )
    parser.add_argument(
        "--numStreams",
        type     = int,
        required = False,
        default  = 1,
        help     = "Number of AXI-Streams in RUDP core",
    )
    parser.add_argument(
        "--sysrefCtrl",
        type     = argBool,
        required = False,
        default  = False,
        help     = "Enable Sysref Ctrl for internal programmable delay",
    )

    # -------------------------------------------------------------------------
    # RoCEv2 arguments
    # -------------------------------------------------------------------------
    parser.add_argument(
        "--useRoce",
        action   = 'store_true',
        default  = False,
        help     = "Use RoCEv2 RDMA for streaming instead of UDP/RSSI",
    )
    parser.add_argument(
        "--useDcqcn",
        action   = 'store_true',
        default  = False,
        help     = "Use RoCEv2 DCQCN for congestion control",
    )
    parser.add_argument(
        "--roceDevice",
        type     = str,
        required = False,
        default  = 'rxe0',
        help     = "ibverbs device name. "
                   "Use 'rxe0' for softRoCE or e.g. 'mlx5_0' for a hardware RoCEv2 NIC. "
                   "Run 'ibv_devinfo' to list available devices. "
                   "Default: rxe0",
    )
    parser.add_argument(
        "--roceGidIndex",
        type     = int,
        required = False,
        default  = -1,
        help     = "GID table index for the host NIC's RoCEv2 IPv4 address. "
                   "Run 'ibv_devinfo -v -d <device> | grep GID' to find the right index. "
                   "-1 = auto-detect from --ip. "
                   "Default: -1 (auto)",
    )
    parser.add_argument(
        "--rocePmtu",
        type     = int,
        required = False,
        default  = IBV_MTU_4096,
        choices  = [IBV_MTU_256, IBV_MTU_512, IBV_MTU_1024, IBV_MTU_2048, IBV_MTU_4096],
        metavar  = '{1=256, 2=512, 3=1024, 4=2048, 5=4096}',
        help     = "Path MTU for the RC QP. Must match the FPGA firmware setting. "
                   "1=256 B  2=512 B  3=1024 B  4=2048 B  5=4096 B. "
                   "Default: 5 (4096 bytes)",
    )
    parser.add_argument(
        "--roceMaxPay",
        type     = int,
        required = False,
        default  = None,
        help     = "Max payload bytes per RDMA WRITE. "
                   "Must be >= the largest single transfer your FPGA will send. "
                   "Default: 9000",
    )
    parser.add_argument(
        "--roceQDepth",
        type     = int,
        required = False,
        default  = None,
        help     = "Number of receive slots (zero-copy queue depth). "
                   "Increase if frames are dropped at high data rates. "
                   "Default: 256",
    )
    parser.add_argument(
        "--roceOffset",
        type     = lambda x: int(x, 0),   # accepts hex (0x...) or decimal
        required = False,
        default  = 0x0000_0000,
        help     = "[meta mode] AXI-lite byte offset of the RoCEv2 engine register block. "
                   "Default: 0x0",
    )

    # -------------------------------------------------------------------------
    # RoCEv2 QP tuning arguments
    # -------------------------------------------------------------------------
    parser.add_argument(
        "--roceMinRnrTimer",
        type     = int,
        required = False,
        default  = 1,
        metavar  = '{0..31}',
        help     = "Minimum RNR timer code embedded in RNR NAK packets sent to the FPGA. "
                   "The FPGA must wait at least this long before retrying after an RNR NAK. "
                   "IB spec: 0=655ms  1=0.01ms  14=1ms  18=4ms  22=16ms  31=491ms. "
                   "Default: 1 (0.01ms)",
    )
    parser.add_argument(
        "--roceRnrRetry",
        type     = int,
        required = False,
        default  = 7,
        metavar  = '{0..7}',
        help     = "Number of times the FPGA retries after receiving an RNR NAK. "
                   "7 = infinite retries (recommended). "
                   "Default: 7",
    )
    parser.add_argument(
        "--roceRetryCount",
        type     = int,
        required = False,
        default  = 3,
        metavar  = '{0..7}',
        help     = "Number of times the FPGA retries after a non-RNR error "
                   "(e.g. timeout, sequence error). "
                   "Default: 3",
    )

    # -------------------------------------------------------------------------
    # Parse and launch
    # -------------------------------------------------------------------------
    args = parser.parse_args()

    if args.useRoce:
        logging.getLogger('pyrogue.Device.RoCEv2Server').setLevel(logging.DEBUG)
        logging.getLogger('pyrogue.Root').setLevel(logging.INFO)

    root = devBoard.Root(
        ip               = args.ip,
        xvcSrvEn         = False,
        # RoCEv2
        useRoce          = args.useRoce,
        useDcqcn         = args.useDcqcn,
        roceDevice       = args.roceDevice,
        roceGidIndex     = args.roceGidIndex,
        rocePmtu         = args.rocePmtu,
        roceMaxPay       = args.roceMaxPay,
        roceQDepth       = args.roceQDepth,
        roceOffset       = args.roceOffset,
        # RoCEv2 QP tuning
        roceMinRnrTimer  = args.roceMinRnrTimer,
        roceRnrRetry     = args.roceRnrRetry,
        roceRetryCount   = args.roceRetryCount,
    )

    with root as hw:
        pr.waitCntrlC()
        # Tear down FPGA QP before the root context manager calls stop()
        # and tears down the UDP transport
        if args.useRoce and hasattr(root, 'rdmaRx') and hasattr(root.rdmaRx, 'teardownFpgaQp'):
            root.rdmaRx.teardownFpgaQp()

