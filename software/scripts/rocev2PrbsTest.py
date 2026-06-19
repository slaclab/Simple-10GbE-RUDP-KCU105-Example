#!/usr/bin/env python3
#-----------------------------------------------------------------------------
# This file is part of the 'Simple-10GbE-RUDP-KCU105-Example'. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the 'Simple-10GbE-RUDP-KCU105-Example', including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------
import setupLibPaths          # MUST be first — adds firmware/python + surf/python to sys.path

import sys
import time
import argparse

import pyrogue
import pyrogue.pydm
import rogue.interfaces.stream as ris

import rocev2_10gbe_rudp_kcu105_example as roceBoard

#################################################################
# Import smoke-test
#
# Touch the two pre-release rogue symbols this launcher relies on
# (RoCEv2Server + PrbsRx). When the wrong rogue environment is sourced
# (stock pyrogue without RoCEv2 support) the attribute access raises and
# we fail loudly with a clear remediation message and a non-zero exit,
# instead of dying with a confusing AttributeError deep inside Root().
#################################################################
try:
    import pyrogue.protocols           # provides RoCEv2Server
    pyrogue.protocols.RoCEv2Server     # attribute-touch to force the failure here
    import pyrogue.utilities.prbs      # provides PrbsRx
    pyrogue.utilities.prbs.PrbsRx
except (ImportError, AttributeError) as e:
    print(
        f"ERROR: pre-release rogue with RoCEv2/PrbsRx not found ({e}).\n"
        f"       source ~/project/rogue/setup_rogue.sh "
        f"(or software/setup_env_slac.sh) before running this script.",
        file=sys.stderr,
    )
    sys.exit(1)

#################################################################
# Path MTU byte-size -> IBV_MTU enum
#################################################################
_PMTU_ENUM = {256: 1, 512: 2, 1024: 3, 2048: 4, 4096: 5}

#################################################################

if __name__ == "__main__":

    # Best-effort graceful teardown on SIGTERM (e.g. terminal/window-manager close):
    # convert it to KeyboardInterrupt so the `with Root(...)` block unwinds into
    # Root.stop(), which disarms the FPGA. SIGINT/exceptions already unwind; the
    # FW auto-reset + clean-slate-on-start are the ultimate backstop for SIGKILL.
    import signal as _signal

    def _sigterm(_signum, _frame):
        raise KeyboardInterrupt

    _signal.signal(_signal.SIGTERM, _sigterm)

    # Convert str to bool
    argBool = lambda s: s.lower() in ['true', 't', 'yes', '1']

    # Set the argument parser
    parser = argparse.ArgumentParser(
        description='RoCEv2 PRBS pass/fail launcher (+ optional PyDM GUI)')

    # Add arguments
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
        "--guiType",
        type     = str,
        required = False,
        default  = 'PyDM',
        help     = "Sets the GUI type (PyDM or None)",
    )

    parser.add_argument(
        "--zmqSrvPort",
        type     = int,
        required = False,
        default  = 9099,
        help     = "Zeromq server port (set to zero if you want it dynamic)",
    )

    parser.add_argument(
        "--target",
        required = False,
        default  = 1000,
        type     = int,
        help     = "Number of PRBS frames to receive before declaring PASS "
                   "(continuous event-driven dispatch)",
    )

    parser.add_argument(
        "--trigRate",
        required = False,
        default  = 2.5e4,
        type     = float,
        help     = "PRBS packet rate in Hz (SsiPrbsTx.TrigRate). Default 2.5e4 is the "
                   "measured clean-validation ceiling on this host: the Python PrbsRx "
                   "consumer (and the rogue zero-copy recv-slot re-post) saturates near "
                   "25-30 kHz (~100 MB/s), well below 10GbE line rate, so above it PRBS "
                   "errors appear -- host-stack limited, NOT a FW issue (the FW reports "
                   "successful completions far beyond this rate). Set 0 to free-run the "
                   "FW at full line rate; the link streams at line rate but the PrbsRx "
                   "validator cannot keep up and will report errors. Full-rate per-frame "
                   "validation needs a faster (non-Python) host consumer.",
    )

    parser.add_argument(
        "--minRnrTimer",
        required = False,
        default  = 12,
        type     = int,
        help     = "IB min_rnr_timer code for native FW<->NIC flow control (12=0.64ms, "
                   "1=0.01ms, 31=491ms). RDMA-SEND-with-immediate is two-sided, so when the "
                   "host recv queue drains the NIC RNR-NAKs the FPGA, which backs off this long "
                   "and retries — self-pacing the source to the host consume rate with NO "
                   "software credit writes in the real-time path. Too small storms RNR NAKs; "
                   "too large collapses throughput. Sweep 8..16 to find the knee.",
    )

    parser.add_argument(
        "--roceGidIndex",
        type     = int,
        required = False,
        default  = None,
        help     = "RoCEv2 GID index. If omitted, auto-detected as the RoCE v2 "
                   "IPv4 GID on --ip's subnet (pass explicitly to override)",
    )

    parser.add_argument(
        "--roceDevice",
        type     = str,
        required = False,
        default  = 'mlx5_0',
        help     = "ibverbs device name (mlx5_0 = HW NIC, rxe0 = softRoCE)",
    )

    parser.add_argument(
        "--len",
        type     = int,
        required = False,
        default  = None,
        help     = "Bytes per RDMA WRITE (default: min(MaxPayload, PMTU) "
                   "floored to a multiple of 32)",
    )

    parser.add_argument(
        "--pmtu",
        type     = int,
        required = False,
        default  = 4096,
        help     = "Path MTU in bytes (256/512/1024/2048/4096)",
    )

    parser.add_argument(
        "--timeout",
        type     = float,
        required = False,
        default  = 10.0,
        help     = "Seconds to poll for completion before declaring FAIL",
    )

    # Get the arguments
    args = parser.parse_args()

    #################################################################
    # Validate / map CLI args before constructing the Root
    #################################################################

    # softRoCE escape hatch — warn loudly but proceed
    if not args.roceDevice.startswith('mlx5'):
        print(
            f"WARNING: --roceDevice='{args.roceDevice}' is not an mlx5_* HW NIC; "
            f"proceeding anyway (softRoCE / bench escape hatch).",
            file=sys.stderr,
        )

    # Map --pmtu bytes -> IBV_MTU enum
    if args.pmtu not in _PMTU_ENUM:
        print(
            f"ERROR: --pmtu={args.pmtu} is not a valid Path MTU "
            f"(choose one of {sorted(_PMTU_ENUM)}).",
            file=sys.stderr,
        )
        sys.exit(1)
    pmtu_enum  = _PMTU_ENUM[args.pmtu]
    pmtu_bytes = args.pmtu

    # --target is the number of frames to receive before PASS; must be positive.
    if args.target < 1:
        print(f"ERROR: --target={args.target} must be >= 1.", file=sys.stderr)
        sys.exit(1)

    # RoCEv2 GID index: explicit --roceGidIndex overrides; -1 lets RoCEv2Server
    # auto-detect the RoCE v2 IPv4 GID on --ip's subnet (the index drifts across
    # FPGA reloads, so it is detected fresh each run).
    gidIndex = args.roceGidIndex if args.roceGidIndex is not None else -1

    # ----------------------------------------------------------------
    # Resolve the INITIAL per-frame Len (bytes per RDMA SEND) up front. Len only sets
    # the STARTING SsiPrbsTx.PacketLength; the FW frames each SEND dynamically from the
    # inbound tLast, so PacketLength may be changed LIVE up to the FW per-SEND cap
    # (MaxSize = one PMTU = 4096 B).
    #
    # Therefore the host recv-WR buffer is sized to the FULL PMTU (roceMaxPay =
    # pmtu_bytes), NOT Len. If it were only Len (e.g. 4064), a larger live PacketLength
    # (e.g. 4072 B) would overflow the recv buffer -> receiver Local Length Error ->
    # the NIC NAKs -> the FW SEND completes with an error -> UnsuccessCounter++. Sizing
    # the buffer to the PMTU lets the host receive any frame up to the FW cap.
    #
    # RDMA-SEND is two-sided: each SEND consumes the next posted recv-WR and lands in
    # THAT buffer; flow control is native (recv queue drains -> NIC RNR-NAKs the FPGA).
    #
    # The PRBS word is 64-bit (8 B) <= the 32-byte RoCEv2 beat. The initial Len is a
    # multiple of 32 (validated below), but a LIVE PacketLength may be any 8-byte-word
    # size up to the cap -- the FW replays a partial final 32-byte beat correctly.
    # ----------------------------------------------------------------
    ROCE_BEAT_BYTES = 32
    gran = ROCE_BEAT_BYTES
    if args.len is None:
        # Default to the full PMTU (= FW MaxSize cap) -> SsiPrbsTx.PacketLength 0x1ff
        # (511 words). 4096 B = 128 full 32-byte replay beats; the dynamic-length FW
        # handles it as a normal SEND.
        Len = pmtu_bytes
    else:
        Len = args.len
        if Len > pmtu_bytes:
            print(
                f"WARNING: --len={Len} > PMTU={pmtu_bytes} — a frame larger than the FW "
                f"per-SEND cap (MaxSize) is DROPPED in FW (OversizeCount) and exceeds one "
                f"RC packet. Proceeding anyway.",
                file=sys.stderr,
            )
    if Len % gran != 0 or Len < 2 * gran:
        print(
            f"ERROR: Len={Len} is invalid — must be a multiple of {gran} bytes "
            f"and >= {2 * gran} bytes.",
            file=sys.stderr,
        )
        sys.exit(1)

    #################################################################

    with roceBoard.Root(
        ip           = args.ip,
        roceDevice   = args.roceDevice,
        roceGidIndex = gidIndex,
        rocePmtu     = pmtu_enum,
        roceMaxPay   = pmtu_bytes,           # host recv buffer = full PMTU = FW MaxSize cap
        roceMinRnrTimer = args.minRnrTimer,  # native RNR backoff (FW<->NIC flow control)
        pollEn       = args.pollEn,
        initRead     = args.initRead,
        zmqSrvPort   = args.zmqSrvPort,
    ) as root:

        # Root.start() already validated the RoCEv2 RC connection is 'Connected'
        # (it raises otherwise), so the engine is up by the time we reach here.
        rx    = root.rdmaRx
        state = rx.ConnectionState.get()

        # ----------------------------------------------------------------
        # Retrieve MR parameters from the RoCEv2Server local variables
        # ----------------------------------------------------------------
        rx_queue_depth = rx.RxQueueDepth.get()
        max_payload    = rx.MaxPayload.get()
        mr_len         = rx_queue_depth * max_payload
        remQpn         = rx.HostQpn.get()
        mrRKey         = rx.MrRkey.get()
        mrAddr         = rx.MrAddr.get()
        locKey         = rx.FpgaLkey.get()

        prbs = root.App.SsiPrbsTx
        dma  = root.App.RoCEv2AxiStreamRdma

        # PRBS data word size in bytes, read from the FW (SsiPrbsTx.WordSize =
        # PRBS_SEED_SIZE_G in bits). PacketLength is counted in these words, so the
        # host tracks the FW config instead of hard-coding the width.
        word_bytes = prbs.WordSize.get() // 8

        # Len was chosen up front and passed as the host maxPayload; validate it
        # against the FW's PRBS word size (PacketLength is counted in whole words).
        if Len % word_bytes != 0:
            print(
                f"ERROR: Len={Len} is not a multiple of the {word_bytes}-byte PRBS "
                f"word — adjust --len or --pmtu.",
                file=sys.stderr,
            )
            sys.exit(1)

        # The host recv-WR buffer (maxPayload = full PMTU) must hold the LARGEST SEND the
        # FW can dispatch, so that ANY live SsiPrbsTx.PacketLength up to the FW cap is
        # received without a Local Length Error (recv buffer overflow -> receiver NAK ->
        # UnsuccessCounter). The FW per-SEND cap is the hardware constant 0x04 MaxSize
        # (RO = MAX_BEATS_C*32 = one PMTU). SEND lands in the next consumed recv-WR.
        fw_max_send = dma.MaxSize.get()
        if max_payload < fw_max_send:
            print(
                f"ERROR: host maxPayload={max_payload} < FW MaxSize={fw_max_send}; recv-WR "
                f"buffer cannot hold the largest SEND (raise --pmtu).",
                file=sys.stderr,
            )
            sys.exit(1)
        if Len > fw_max_send:
            print(
                f"ERROR: initial Len={Len} exceeds the FW per-SEND cap MaxSize={fw_max_send} "
                f"(MAX_BEATS_C*32) — reduce --len/--pmtu.",
                file=sys.stderr,
            )
            sys.exit(1)

        # ----------------------------------------------------------------
        # Set UDP engine destination (host IP from RoCEv2Server.HostIp)
        # ----------------------------------------------------------------
        hostIp = rx.HostIp.get()
        print(f"Setting UDP engine destination to {hostIp}:4791")
        root.Core.UdpEngine.ClientRemotePort[0].set(4791)
        root.Core.UdpEngine.ClientRemoteIp[0].set(hostIp)

        print(
            f"--- RoCEv2 PRBS run parameters ---\n"
            f"  ConnectionState : {state}\n"
            f"  Host QPN        : {hex(remQpn)}\n"
            f"  Host GID        : {rx.HostGid.get()}\n"
            f"  MR addr         : {hex(mrAddr)}\n"
            f"  MR rkey         : {hex(mrRKey)}\n"
            f"  FPGA lkey       : {hex(locKey)}\n"
            f"  MaxPayload      : {max_payload}\n"
            f"  RxQueueDepth    : {rx_queue_depth}\n"
            f"  MrLen           : {mr_len}\n"
            f"  Len (per msg)   : {Len}\n"
            f"  FW MaxSize cap  : {fw_max_send}\n"
            f"  PMTU            : {pmtu_bytes}\n"
            f"  Target frames   : {args.target}\n"
            f"----------------------------------"
        )

        # ----------------------------------------------------------------
        # Configure the PRBS source + DMA dispatch registers
        # ----------------------------------------------------------------
        # PacketLength is in PRBS words: (Len // word_bytes) - 1. This may be changed
        # LIVE in the GUI: the FW frames each SEND from the inbound tLast (no Len
        # register) and handles a partial final 32-byte beat, so the RDMA path tracks
        # ANY dynamic PacketLength up to the FW cap (MaxSize = one PMTU) without a
        # restart and with no 32-byte-multiple requirement. The host recv buffer is the
        # full PMTU, so every such frame is received.
        prbs.PacketLength.set(Len // word_bytes - 1)

        # PRBS packet rate. TrigDly=0 free-runs at full line rate; a positive
        # --trigRate throttles the source so the host receive path keeps up
        # (avoids overrun + PRBS continuity errors during a continuous run).
        if args.trigRate > 0:
            prbs.TrigRate.set(args.trigRate)
        else:
            prbs.TrigDly.set(0)

        dma.LKey.set(locKey)
        dma.SQpn.set(remQpn)
        dma.AddrWrapCount.set(mr_len // Len)
        # dma.DQpn left at default 0 — UD-datagram field, unused by the RC SEND path.
        # RKey/RemAddr are legacy RETH registers; RDMA-SEND drives rAddr/rKey to 0 in
        # the FW, so they are intentionally not configured here.

        # ----------------------------------------------------------------
        # Dual counter reset (FW + host) — RemoteCommand toggles, never .set(0/1/0)
        # ----------------------------------------------------------------
        dma.ResetCounters()        # zeroes FW SuccessCounter/UnsuccessCounter
        root.CountReset()          # zeroes host PrbsRx rxErrors/rxCount/rxBytes

        # ----------------------------------------------------------------
        # Event-driven continuous run.
        #
        # DispatchEnable arms the FW dispatcher; TxEn free-runs the PRBS source
        # (AXI_EN_G='1' means the host owns the trigger, so without TxEn the FIFO
        # stays empty and nothing dispatches). With both set the FW issues one RDMA
        # SEND per complete buffered PRBS packet continuously — no per-frame poke.
        #
        # Flow control is entirely native FW<->NIC: there is NO software credit feed
        # in the real-time path. RDMA-SEND is two-sided, so when the host recv queue
        # drains the NIC RNR-NAKs the FPGA; the blue-rdma SQ stalls and retries
        # (rnr_retry=7 infinite, min_rnr_timer=--minRnrTimer) and backpressures the
        # dispatcher, which fills the repack FIFO and throttles the PRBS source. The
        # host thread's only job is to post/consume recv-WRs at its own pace.
        # ----------------------------------------------------------------
        print(f"Streaming until rxCount >= {args.target} ({Len} bytes/frame, "
              f"native RNR flow control, minRnrTimer={args.minRnrTimer})...")
        dma.DispatchEnable.set(True)
        prbs.TxEn.set(True)

        # ----------------------------------------------------------------
        # Poll rxCount to the target — the receiver fills continuously
        # ----------------------------------------------------------------
        deadline = time.monotonic() + args.timeout
        while root.PrbsRx.rxCount.get() < args.target:
            if time.monotonic() > deadline:
                print(f"WARNING: timed out after {args.timeout}s waiting for "
                      f"rxCount >= {args.target}", file=sys.stderr)
                break                       # fall through to the assert; do NOT raise
            time.sleep(0.05)                # poll interval, NOT a completion sleep

        # ----------------------------------------------------------------
        # Stop the stream (disarm dispatch first, then quiesce the PRBS source)
        # ----------------------------------------------------------------
        dma.DispatchEnable.set(False)
        prbs.TxEn.set(False)

        # ----------------------------------------------------------------
        # Assert — cannot false-green on zero frames
        # ----------------------------------------------------------------
        errs    = root.PrbsRx.rxErrors.get()
        rxCount = root.PrbsRx.rxCount.get()
        success = dma.SuccessCounter.get()
        passed  = (errs == 0) and (rxCount >= args.target)

        print(
            f"--- PRBS result ---\n"
            f"  PrbsRx.rxErrors        : {errs}\n"
            f"  PrbsRx.rxCount         : {rxCount} (target {args.target})\n"
            f"  Dma.SuccessCounter     : {success}\n"
            f"  RESULT                 : {'PASS' if passed else 'FAIL'}\n"
            f"-------------------"
        )

        ######################
        # Development PyDM GUI
        ######################
        if (args.guiType == 'PyDM'):
            # Re-arm the stream so the operator sees rxCount climbing live in the
            # GUI. Toggle App.SsiPrbsTx.TxEn (or App.RoCEv2AxiStreamRdma.DispatchEnable)
            # to start/stop continuous reception. Flow control stays native FW<->NIC
            # (RNR) — there is no credit feeder to restart.
            dma.ResetCounters()        # zero FW SuccessCounter/UnsuccessCounter
            root.CountReset()          # zero host rxErrors/rxCount/rxBytes
            dma.DispatchEnable.set(True)
            prbs.TxEn.set(True)
            # Zero the counters again right before the GUI opens so the operator starts
            # from a clean slate (the re-arm above streamed frames during setup).
            # root.CountReset() cascades to the FW counters too (RoCEv2AxiStreamRdma
            # overrides countReset() -> ResetCounters).
            root.CountReset()
            pyrogue.pydm.runPyDM(
                serverList = root.zmqServer.address,
                sizeX      = 800,
                sizeY      = 800,
            )
            # Propagate the pass/fail code once the operator closes the GUI, so
            # the default path never returns exit 0 on a FAIL run.
            sys.exit(0 if passed else 1)

        #################
        # No GUI — headless, exit with the pass/fail code
        #################
        elif (args.guiType == 'None'):
            sys.exit(0 if passed else 1)

        ####################
        # Undefined GUI type
        ####################
        else:
            raise ValueError("Invalid GUI type (%s)" % (args.guiType))

    #################################################################
