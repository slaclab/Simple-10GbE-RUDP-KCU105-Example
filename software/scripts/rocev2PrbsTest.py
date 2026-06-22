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

import rocev2_10gbe_rudp_kcu105_example as roceBoard

#################################################################

if __name__ == "__main__":

    # Convert SIGTERM (terminal/WM close) to KeyboardInterrupt so the
    # `with Root(...)` block unwinds into Root.stop() and tears down the FPGA QP.
    # SIGINT/exceptions already unwind; SIGKILL relies on the FW auto-reset backstop.
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
        "--p2p",
        type     = argBool,
        required = False,
        default  = False,
        help     = "Point-to-point bring-up switch: bypasses FW DCQCN "
                   "(DcqcnBypass=True) and forces minimal RNR backoff "
                   "(minRnrTimer=1), overriding any explicit --minRnrTimer. "
                   "Couples both halves of the P2P fix into one flag.",
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

    # --target is the number of frames to receive before PASS; must be positive.
    if args.target < 1:
        print(f"ERROR: --target={args.target} must be >= 1.", file=sys.stderr)
        sys.exit(1)

    # RoCEv2 GID index: explicit --roceGidIndex overrides; -1 lets RoCEv2Server
    # auto-detect the RoCE v2 IPv4 GID on --ip's subnet (the index drifts across
    # FPGA reloads, so it is detected fresh each run).
    gidIndex = args.roceGidIndex if args.roceGidIndex is not None else -1

    # Build the host-NIC config from the CLI args. The cfg defaults
    # (maxPayload=4096, pmtu=MTU_4096) fix the 4096B framing — host recv buffer
    # = full PMTU = FW MaxSize cap — so only the device/GID knobs are set here.
    rocev2Cfg = pyrogue.protocols.RoCEv2ServerCfg(
        ip          = args.ip,
        deviceName  = args.roceDevice,
        gidIndex    = gidIndex,
    )

    # Transport / QP-tuning config. The single instance is forwarded by the Root
    # into BOTH engine.setupConnection() and server.completeConnection() so the
    # FPGA and host sides cannot drift. --minRnrTimer is the native RNR backoff
    # (FW<->NIC flow control); the remaining knobs (pmtu/rnrRetry/retryCount)
    # keep their proven acceptance-gate defaults.
    #
    # --p2p (D-07) forces minimal RNR backoff (code 1), unconditionally
    # overriding any --minRnrTimer value. Notify the operator if --minRnrTimer
    # was also passed with a non-default value so the override leaves an audit
    # line (the DcqcnBypass=True half is applied live below via setP2pMode).
    minRnrTimer = args.minRnrTimer
    if args.p2p:
        if args.minRnrTimer != 12:
            print(
                f"NOTICE: --p2p overrode --minRnrTimer={args.minRnrTimer} to 1 "
                f"(minimal RNR backoff for point-to-point).",
                file=sys.stderr,
            )
        minRnrTimer = 1

    transportCfg = pyrogue.protocols.RoCEv2TransportCfg(
        minRnrTimer = minRnrTimer,
    )

    #################################################################

    with roceBoard.Root(
        rocev2Cfg    = rocev2Cfg,
        transportCfg = transportCfg,
        pollEn       = args.pollEn,
        initRead     = args.initRead,
        zmqSrvPort   = args.zmqSrvPort,
    ) as root:

        # Root.start() already ran the host<->FPGA bring-up; the RoCEv2 engine is
        # connected-but-idle here. Arming the source (DispatchEnable/TxEn) is below.
        rx = root.rdmaRx

        # --p2p: enable the FW DCQCN bypass LIVE through the SW-03 helper so both
        # halves of the P2P fix live in one place. setP2pMode also records the
        # minimal RNR code for the next bring-up; the RNR=1 minimization for THIS
        # run was already applied via transportCfg above (forwarded into the QP
        # hand-off during start()).
        if args.p2p:
            root.setP2pMode(True)

        # MR parameters from the RoCEv2Server local variables. Per-frame length =
        # host maxPayload (full PMTU = FW MaxSize cap); this is the STARTING
        # SsiPrbsTx.PacketLength, changeable LIVE in the GUI up to the FW cap.
        rx_queue_depth = rx.RxQueueDepth.get()
        max_payload    = rx.MaxPayload.get()
        mr_len         = rx_queue_depth * max_payload
        Len            = max_payload
        remQpn         = rx.HostQpn.get()
        locKey         = rx.FpgaLkey.get()

        prbs = root.App.SsiPrbsTx
        dma  = root.Core.RoCEv2Engine.Rdma

        # PRBS word size in bytes (SsiPrbsTx.WordSize = PRBS_SEED_SIZE_G bits), read
        # from the FW so the host tracks its config. PacketLength counts whole words,
        # so the per-frame length must be a multiple of it.
        word_bytes = prbs.WordSize.get() // 8

        if Len % word_bytes != 0:
            print(
                f"ERROR: maxPayload={Len} is not a multiple of the {word_bytes}-byte PRBS "
                f"word — incompatible FW PRBS_SEED_SIZE_G.",
                file=sys.stderr,
            )
            sys.exit(1)

        # The host recv-WR buffer (maxPayload = full PMTU) must hold the LARGEST SEND
        # the FW can dispatch, else a too-large SEND overflows it (Local Length Error
        # -> receiver NAK -> UnsuccessCounter). FW per-SEND cap = the RO MaxSize
        # register (MAX_BEATS_C*32 = one PMTU).
        fw_max_send = dma.MaxSize.get()
        if max_payload < fw_max_send:
            print(
                f"ERROR: host maxPayload={max_payload} < FW MaxSize={fw_max_send}; recv-WR "
                f"buffer cannot hold the largest SEND (FW MaxSize exceeds maxPayload).",
                file=sys.stderr,
            )
            sys.exit(1)
        if Len > fw_max_send:
            print(
                f"ERROR: maxPayload={Len} exceeds the FW per-SEND cap MaxSize={fw_max_send} "
                f"(MAX_BEATS_C*32).",
                file=sys.stderr,
            )
            sys.exit(1)

        # ----------------------------------------------------------------
        # Configure the PRBS source + DMA dispatch registers
        # ----------------------------------------------------------------
        # PacketLength in PRBS words: (Len // word_bytes) - 1. Changeable LIVE in the
        # GUI — the FW frames each SEND from the inbound tLast (no Len register) and
        # handles a partial final beat, so any value up to the FW cap is received.
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
        # Event-driven continuous run. DispatchEnable arms the FW dispatcher; TxEn
        # free-runs the PRBS source (AXI_EN_G='1' => host owns the trigger). With both
        # set the FW issues one RDMA SEND per complete buffered PRBS packet — no
        # per-frame poke.
        #
        # Flow control is entirely native FW<->NIC (no software credit feed): a full
        # host recv queue RNR-NAKs the FPGA; the blue-rdma SQ stalls/retries
        # (rnr_retry=7, min_rnr_timer=--minRnrTimer), backpressuring the dispatcher ->
        # repack FIFO -> PRBS source. The host only posts/consumes recv-WRs at its pace.
        # ----------------------------------------------------------------
        print(f"Streaming until rxCount >= {args.target} ({Len} bytes/frame, "
              f"native RNR flow control, minRnrTimer={minRnrTimer}, "
              f"p2p={args.p2p})...")
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
            # Re-arm the stream so the operator sees rxCount climbing live; toggle
            # TxEn / DispatchEnable in the GUI to start/stop. Flow control stays
            # native FW<->NIC (RNR) — no credit feeder to restart.
            dma.ResetCounters()        # zero FW SuccessCounter/UnsuccessCounter
            root.CountReset()          # zero host rxErrors/rxCount/rxBytes
            dma.DispatchEnable.set(True)
            prbs.TxEn.set(True)
            # Re-zero right before the GUI opens (the re-arm above streamed frames
            # during setup). root.CountReset() cascades to the FW counters too.
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
