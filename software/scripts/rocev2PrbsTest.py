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
        default  = True,
        help     = "Point-to-point bring-up switch (DEFAULT True for the switchless "
                   "bench): forces Not-ECT egress + no DSCP marking, bypasses FW DCQCN "
                   "(DcqcnBypass=True), and forces minimal RNR backoff (minRnrTimer=1), "
                   "overriding any explicit --minRnrTimer. Pass --p2p false for a managed "
                   "ECN fabric, then tune --dscp/--ecn/--enableDcqcn.",
    )

    parser.add_argument(
        "--dscp",
        type     = int,
        required = False,
        default  = 26,
        help     = "Managed-fabric only (ignored when --p2p true): IP-header DSCP for "
                   "TX packets (0-63). Default 26 = AF31; set to match the switch "
                   "lossless/ECN traffic class.",
    )

    parser.add_argument(
        "--ecn",
        type     = int,
        required = False,
        default  = 2,
        help     = "Managed-fabric only (ignored when --p2p true): IP-header ECN field "
                   "(0=Not-ECT, 1=ECT(1), 2=ECT(0)/b\"10\", 3=CE). Default 2 = ECT(0) "
                   "opts the flow into the fabric's ECN/DCQCN congestion control.",
    )

    parser.add_argument(
        "--enableDcqcn",
        type     = argBool,
        required = False,
        default  = True,
        help     = "Managed-fabric only (ignored when --p2p true): run FW DCQCN "
                   "congestion control (False bypasses it via DcqcnBypass).",
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

    # Transport / QP-tuning config. The Root forwards the single instance into BOTH
    # engine.setupConnection() and server.completeConnection() so the FPGA and host
    # cannot drift. --minRnrTimer is the native RNR backoff (FW<->NIC flow control);
    # pmtu/rnrRetry/retryCount keep their proven acceptance-gate defaults.
    #
    # --p2p forces minimal RNR backoff (code 1), overriding any --minRnrTimer; log an
    # audit line if a non-default --minRnrTimer was also passed. (The Not-ECT +
    # DcqcnBypass halves are applied in Root.start() from the args forwarded below.)
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
        p2p          = args.p2p,
        dscp         = args.dscp,
        ecn          = args.ecn,
        enableDcqcn  = args.enableDcqcn,
        pollEn       = args.pollEn,
        initRead     = args.initRead,
        zmqSrvPort   = args.zmqSrvPort,
    ) as root:

        # Root.start() already ran the host<->FPGA bring-up; the RoCEv2 engine is
        # connected-but-idle here, and the egress ECN/DSCP + DCQCN-bypass posture
        # (p2p vs managed fabric) was applied inside start() from the args above.
        # Arming the source (DispatchEnable/TxEn) is below.
        rx = root.rdmaRx

        # MR parameters from the RoCEv2Server local variables. The on-wire RDMA SEND =
        # one full PMTU (= host maxPayload = FW MaxSize cap). The FW AxiStreamPacketizer2
        # adds a 16B hdr+tail per frame, so the raw PRBS payload is one PMTU minus that
        # overhead and raw + overhead = the PMTU-sized SEND.
        PKTZR_OVERHEAD = 16  # AxiStreamPacketizer2 header word + tail word (CRC_MODE_G="NONE")
        rx_queue_depth = rx.RxQueueDepth.get()
        max_payload    = rx.MaxPayload.get()
        mr_len         = rx_queue_depth * max_payload
        Len            = max_payload                  # on-wire SEND size (packetized frame)
        raw_payload    = max_payload - PKTZR_OVERHEAD  # raw PRBS payload seen by PrbsRx after depacketize
        remQpn         = rx.HostQpn.get()
        locKey         = rx.FpgaLkey.get()

        prbs  = root.App.SsiPrbsTx
        dma   = root.Core.RoCEv2AxiStreamRdma.Core
        dcqcn = root.Core.RoCEv2AxiStreamRdma.Dcqcn   # FW telemetry: Rc/Rt/CnpCounter (RO, pollInterval=1)

        # PRBS word size in bytes (SsiPrbsTx.WordSize = PRBS_SEED_SIZE_G bits), read
        # from the FW so the host tracks its config. PacketLength counts whole words,
        # so the raw PRBS payload (PMTU minus packetizer overhead) must be a multiple of it.
        word_bytes = prbs.WordSize.get() // 8

        if raw_payload % word_bytes != 0:
            print(
                f"ERROR: raw payload={raw_payload} (maxPayload {max_payload} - {PKTZR_OVERHEAD}B "
                f"packetizer overhead) is not a multiple of the {word_bytes}-byte PRBS word "
                f"— incompatible FW PRBS_SEED_SIZE_G.",
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
        # PacketLength in PRBS words: (raw_payload // word_bytes) - 1, sized so the
        # packetized SEND lands at exactly one PMTU. Changeable LIVE in the GUI — the FW
        # frames each SEND from the inbound tLast (no Len register), partial beats OK.
        prbs.PacketLength.set(raw_payload // word_bytes - 1)

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
        print(f"Streaming until rxCount >= {args.target} ({raw_payload}B raw / {Len}B on-wire "
              f"per frame, native RNR flow control, minRnrTimer={minRnrTimer}, "
              f"p2p={args.p2p})...")

        # Line-rate run (--trigRate <= 0, same condition that set TrigDly=0): blind the
        # host payload validator. The Python PrbsRx consumer saturates ~25-30 kHz and
        # cannot keep up at line rate, so per-frame checking would report spurious
        # errors; throughput is gated on FW MonBandwidth instead of rxErrors. checkPayload
        # is a live rogue RW LocalVariable, so this propagates to the C++ engine at
        # runtime. Throttled runs (--trigRate > 0) keep the default (True), unchanged.
        if args.trigRate <= 0:
            print("NOTICE: line-rate run — disabling host PrbsRx.checkPayload "
                  "(rxErrors NOT gated; FW MonBandwidth is the throughput gate).",
                  file=sys.stderr)
            root.PrbsRx.checkPayload.set(False)

        dma.DispatchEnable.set(True)
        prbs.TxEn.set(True)

        # ----------------------------------------------------------------
        # Poll rxCount to the target — the receiver fills continuously
        # ----------------------------------------------------------------
        # FW-telemetry trajectory sampler: snapshot (t_rel, Rc, Rt, CnpCounter,
        # MonBandwidth) into `traj` at a ~0.5 s cadence so a line-rate run captures the
        # Rc collapse trajectory (e.g. Rc LINE/2->Rmin under DCQCN throttle), not just an
        # endpoint. A monotonic `nextSample` deadline keeps the 0.05 s rxCount poll
        # cadence and timeout/break semantics below unchanged. Reads hit the
        # pollInterval=1 register cache; rxCount stays a liveness loop condition only.
        SAMPLE_PERIOD = 0.5
        traj      = []
        loopStart = time.monotonic()

        def _sample():
            traj.append((
                time.monotonic() - loopStart,   # t_rel (s)
                dcqcn.Rc.get(),                  # Rc  (Byte/s)
                dcqcn.Rt.get(),                  # Rt  (Byte/s)
                dcqcn.CnpCounter.get(),          # CnpCounter (count)
                dma.MonBandwidth.get(),          # MonBandwidth (Gb/s)
            ))

        _sample()                               # seed: >=1 sample even on an instant timeout
        nextSample = loopStart + SAMPLE_PERIOD

        deadline = time.monotonic() + args.timeout
        while root.PrbsRx.rxCount.get() < args.target:
            if time.monotonic() > deadline:
                print(f"WARNING: timed out after {args.timeout}s waiting for "
                      f"rxCount >= {args.target}", file=sys.stderr)
                break                       # fall through to the assert; do NOT raise
            if time.monotonic() >= nextSample:
                _sample()
                nextSample += SAMPLE_PERIOD
            time.sleep(0.05)                # poll interval, NOT a completion sleep

        # ----------------------------------------------------------------
        # Stop the stream (disarm dispatch first, then quiesce the PRBS source)
        # ----------------------------------------------------------------
        dma.DispatchEnable.set(False)
        prbs.TxEn.set(False)

        # ----------------------------------------------------------------
        # Liveness record (PRBS host counters). For the throttled run rxErrors is
        # the integrity gate; for line-rate runs checkPayload is off so rxErrors is
        # host-stack noise and rxCount stays a liveness precondition (frames flowed).
        # ----------------------------------------------------------------
        errs    = root.PrbsRx.rxErrors.get()
        rxCount = root.PrbsRx.rxCount.get()
        success = dma.SuccessCounter.get()

        # ----------------------------------------------------------------
        # FW-telemetry verdict: for line-rate runs MonBandwidth (FW egress) is the
        # throughput source of truth, NOT rxErrors. Numeric bands in Byte/s (Rc) and
        # Gb/s (Mon).
        # ----------------------------------------------------------------
        LINE_RATE_BPS = 1250000000      # 10 Gb/s in Byte/s — Rc pinned here under bypass

        # If the run timed out instantly the loop body never sampled past the seed;
        # `traj` always holds >=1 entry (seeded at loop entry), but guard anyway by
        # taking one live snapshot so the summary never indexes an empty list.
        if not traj:
            _sample()

        rc_traj   = [s[1] for s in traj]
        cnp_traj  = [s[3] for s in traj]
        mon_traj  = [s[4] for s in traj]
        rc_start  = rc_traj[0]
        rc_min    = min(rc_traj)
        rc_max    = max(rc_traj)
        rc_last   = rc_traj[-1]
        cnp_peak  = max(cnp_traj)
        mon_steady = mon_traj[-1]       # last MonBandwidth Gb/s sample (steady state)

        bps2gbps = lambda b: b * 8.0 / 1.0e9    # same conversion MonBandwidth uses

        # ----------------------------------------------------------------
        # Verdict — selected by run type:
        #
        #  * Throttled / default (--trigRate > 0, checkPayload=True): per-frame
        #    integrity test — PASS = zero PRBS errors AND target frames received.
        #    rxErrors is the source of truth; the FW-telemetry block is informational.
        #
        #  * Line-rate (--trigRate <= 0, checkPayload off): PrbsRx is blinded, so the
        #    verdict gates on FW egress MonBandwidth with rxCount>=target as a liveness
        #    precondition. --p2p additionally requires Rc pinned at LINE_RATE; the
        #    baseline branch reports Rc/CnpCounter for collapse analysis but does not
        #    gate on them (no switch to CE-mark traffic on a switchless bench, so DCQCN
        #    sees no CNPs and baseline holds line rate).
        # ----------------------------------------------------------------
        live = (rxCount >= args.target)

        if args.trigRate > 0:
            # Throttled / default: per-frame-integrity verdict.
            gate_band = "throttled per-frame integrity: rxErrors==0 AND rxCount>=target"
            passed = (errs == 0) and live
        elif args.p2p:
            # Line-rate --p2p PASS: DCQCN bypassed -> Rc pinned at LINE_RATE, FW egress
            # near line rate (margin under 9.7 for RoCEv2/UDP/IP/ETH overhead). This PASS
            # demonstrates order-independence as a consequence — once DCQCN cannot
            # throttle (Rc=LINE_RATE), throughput no longer depends on CNP/arm timing.
            gate_band = "line-rate p2p PASS: MonBandwidth>9.0 Gb/s AND Rc==LINE_RATE"
            passed = live and (mon_steady > 9.0) and (rc_last == LINE_RATE_BPS)
        else:
            # Line-rate baseline measurement: PASS = sustained near-line-rate FW egress.
            # Rc/CnpCounter are reported in the FW-telemetry block for collapse analysis
            # but are NOT gated (the collapse stimulus is bench-topology dependent).
            gate_band = "line-rate baseline: MonBandwidth>9.0 Gb/s (FW egress)"
            passed = live and (mon_steady > 9.0)

        if args.trigRate > 0:
            run_mode = "throttled"
        elif args.p2p:
            run_mode = "--p2p (line-rate)"
        else:
            run_mode = "baseline (line-rate)"

        print(
            f"--- PRBS result ---\n"
            f"  PrbsRx.rxErrors        : {errs}\n"
            f"  PrbsRx.rxCount         : {rxCount} (target {args.target})\n"
            f"  Dma.SuccessCounter     : {success}\n"
            f"  RESULT                 : {'PASS' if passed else 'FAIL'}\n"
            f"-------------------"
        )

        print(
            f"--- FW telemetry ---\n"
            f"  run mode               : {run_mode}\n"
            f"  trajectory samples     : {len(traj)} (cadence {SAMPLE_PERIOD}s)\n"
            f"  Dcqcn.Rc start         : {rc_start} B/s ({bps2gbps(rc_start):0.3f} Gb/s)\n"
            f"  Dcqcn.Rc min           : {rc_min} B/s ({bps2gbps(rc_min):0.3f} Gb/s)\n"
            f"  Dcqcn.Rc max           : {rc_max} B/s ({bps2gbps(rc_max):0.3f} Gb/s)\n"
            f"  Dcqcn.Rc last          : {rc_last} B/s ({bps2gbps(rc_last):0.3f} Gb/s)\n"
            f"  Dcqcn.CnpCounter peak  : {cnp_peak}\n"
            f"  Rdma.MonBandwidth      : {mon_steady:0.3f} Gb/s (FW egress, steady)\n"
            f"  gate band              : {gate_band}\n"
            f"  VERDICT                : {'PASS' if passed else 'FAIL'}\n"
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
