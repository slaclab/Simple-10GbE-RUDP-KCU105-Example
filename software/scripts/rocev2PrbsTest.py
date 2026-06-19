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
# Path MTU byte-size -> IBV_MTU enum (inverse of _Root._MTU_BYTES)
#################################################################
_PMTU_ENUM = {256: 1, 512: 2, 1024: 3, 2048: 4, 4096: 5}

#################################################################
# Capturing stream Slave (counter-mode byte-order check)
#
# Taps root.rdmaStream additively (coexists with PrbsRx + dataWriter ch1)
# and records the raw RDMA payload bytes of every received frame so the
# counter-mode byte-order check can assert the per-beat 32-bit increment.
# Mirrors the fileReader.py ContiguityChecker/HexDumper _acceptFrame idiom.
#################################################################
class _MrCapture(ris.Slave):
    def __init__(self):
        super().__init__()
        self.frames = []

    def _acceptFrame(self, frame):
        with frame.lock():
            ba = bytearray(frame.getPayload())
            frame.read(ba, 0)
            self.frames.append(bytes(ba))

#################################################################
# RoCE v2 GID-index auto-detect
#
# The mlx5 GID-table index of the RoCE v2 IPv4 GID drifts across FPGA reloads,
# so resolve it fresh from sysfs each run (pre-connect, no Root needed). Match
# the entry whose type is RoCE v2 AND whose IPv4-mapped GID (::ffff:a.b.c.d) is
# on the same /24 as --ip — this skips the RoCE v1 slot that shares the same IP.
#################################################################
def detect_roce_gid_index(device, ip, port=1):
    import glob, os
    subnet  = ip.rsplit('.', 1)[0] + '.'
    typ_dir = f'/sys/class/infiniband/{device}/ports/{port}/gid_attrs/types'
    gid_dir = f'/sys/class/infiniband/{device}/ports/{port}/gids'
    for tpath in sorted(glob.glob(f'{typ_dir}/*'),
                        key=lambda p: int(os.path.basename(p))):
        idx = int(os.path.basename(tpath))
        try:
            with open(tpath) as f:
                if f.read().strip() != 'RoCE v2':
                    continue
            with open(f'{gid_dir}/{idx}') as f:
                groups = f.read().strip().split(':')
        except OSError:
            continue
        # IPv4-mapped GID: 0000:0000:0000:0000:0000:ffff:HHHH:LLLL
        if len(groups) != 8 or groups[5].lower() != 'ffff':
            continue
        hi, lo = int(groups[6], 16), int(groups[7], 16)
        ipv4 = f'{hi >> 8}.{hi & 0xff}.{lo >> 8}.{lo & 0xff}'
        if ipv4.startswith(subnet):
            return idx
    return None

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
        "--counterMode",
        type     = argBool,
        required = False,
        default  = False,
        help     = "run the pre-PRBS counter-mode byte-order check "
                   "(FwCnt=True, tap rdmaStream, assert per-beat 32-bit increment)",
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

    # Resolve the RoCEv2 GID index: explicit --roceGidIndex overrides; otherwise
    # auto-detect the RoCE v2 IPv4 GID on --ip's subnet (the index drifts across
    # FPGA reloads, so detect it fresh each run).
    if args.roceGidIndex is not None:
        gidIndex = args.roceGidIndex
    else:
        gidIndex = detect_roce_gid_index(args.roceDevice, args.ip)
        if gidIndex is None:
            print(
                f"ERROR: could not auto-detect a RoCE v2 IPv4 GID on "
                f"{args.roceDevice} matching {args.ip}'s subnet — pass "
                f"--roceGidIndex explicitly (see: ibv_devinfo -v -d {args.roceDevice}).",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Auto-detected --roceGidIndex {gidIndex} "
              f"(RoCE v2 IPv4 GID on {args.roceDevice})")

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

        # ----------------------------------------------------------------
        # Validate connection state
        # ----------------------------------------------------------------
        rx    = root.rdmaRx
        state = rx.ConnectionState.get()
        if state != 'Connected':
            print(f"ERROR: RoCEv2 not connected (state={state}) — aborting",
                  file=sys.stderr)
            sys.exit(1)

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
        # Set UDP engine destination
        # Derive the host IP from the IPv4-mapped HostGid (last 4 bytes)
        # ----------------------------------------------------------------
        gidWords = rx.HostGid.get().split(':')
        hostIp   = '.'.join(str(b) for b in bytes.fromhex(gidWords[-2] + gidWords[-1]))
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
        # Counter-mode byte-order check (pre-PRBS).
        #
        # Toggle SsiPrbsTx.FwCnt (runtime counter mode), tap root.rdmaStream
        # with a capturing Slave, dispatch the same burst as the PRBS path, and
        # assert the per-beat 32-bit-WORD increment with a zeroed upper-224b
        # lane-swap detector. The ramp is a 32-bit count word in tData(31:0),
        # NOT a per-byte ramp.
        # ----------------------------------------------------------------
        if args.counterMode:

            # Additive tap — coexists with the already-wired PrbsRx / dataWriter ch1
            cap = _MrCapture()
            root.rdmaStream >> cap

            # Same register config as the PRBS path
            prbs.PacketLength.set(Len // word_bytes - 1)
            if args.trigRate > 0:
                prbs.TrigRate.set(args.trigRate)
            else:
                prbs.TrigDly.set(0)
            prbs.FwCnt.set(True)       # counter mode (runtime; 0x00[5])
            prbs.TxEn.set(True)        # enable the source (else it never free-runs)

            # No frame-size register to program: the FW derives each SEND's length
            # per-packet from the inbound tLast (0x04 MaxSize is a read-only cap).
            dma.RKey.set(mrRKey)
            dma.LKey.set(locKey)
            dma.SQpn.set(remQpn)
            dma.RemAddr.set(mrAddr)
            dma.AddrWrapCount.set(mr_len // Len)
            # dma.DQpn left at default 0 — UD-datagram field, unused by the RC WRITE path.

            dma.ResetCounters()        # RemoteCommand toggle — zeroes FW counters
            root.CountReset()          # zeroes host PrbsRx counters

            print(f"Counter-mode: capturing {args.target} frame(s) of {Len} bytes "
                  f"(continuous dispatch)...")
            dma.DispatchEnable.set(True)   # arm event-driven dispatch

            # Poll until enough frames captured — fall through to assert on timeout, never raise
            deadline = time.monotonic() + args.timeout
            while len(cap.frames) < args.target:
                if time.monotonic() > deadline:
                    print(f"WARNING: timed out after {args.timeout}s waiting for "
                          f"counter-mode capture (SuccessCounter="
                          f"{dma.SuccessCounter.get()}, frames={len(cap.frames)})",
                          file=sys.stderr)
                    break
                time.sleep(0.05)

            # Stop the stream before inspecting the captured frames.
            dma.DispatchEnable.set(False)
            prbs.TxEn.set(False)

            # ------------------------------------------------------------
            # Increment assertion — 32-bit counter ramp, one beat per PRBS word.
            #  - beat = one PRBS word (word_bytes). beat0 = eventCnt/seed,
            #    beat1 = packetLength, then data beats hold a strictly +1 32-bit
            #    count in the low 4 bytes with the upper bytes zero.
            #  - upper bytes non-zero => a REPACK byte-lane swap.
            # ------------------------------------------------------------
            passed = len(cap.frames) > 0       # zero-frame guard (cannot false-green)
            fail_reason = None if passed else "no frames captured"
            dump_lines = []

            for fi, fr in enumerate(cap.frames):
                beats = [fr[i:i + word_bytes] for i in range(0, len(fr), word_bytes)]
                prev = None
                for n, b in enumerate(beats):
                    valid    = len(b)
                    # Each PRBS word arrives little-endian on the RDMA payload
                    # (the surf/rogue tData convention, after the FW endianSwap):
                    # the counter is the FIRST 4 bytes and the remaining upper
                    # bytes must be zero for a clean ramp.
                    word     = int.from_bytes(b, 'little')
                    low32    = word & 0xFFFFFFFF
                    upper    = word >> 32
                    upper_nz = (upper != 0)
                    role     = 'seed' if n == 0 else ('len ' if n == 1 else 'data')
                    dump_lines.append(f"    f{fi} beat{n:<2} [{role}] valid={valid:<2} "
                                      f"low32=0x{low32:08x} "
                                      f"upper={'NONZERO' if upper_nz else 'zero'} "
                                      f"hex={b.hex()}")

                    # Keep dumping all beats even after a failure, but stop checking.
                    if fail_reason is not None:
                        continue

                    # Lane-swap detector + increment check apply to DATA beats only
                    # (n >= 2); beat0 (seed/eventCnt) and beat1 (packetLength) are
                    # framing words. Len is a whole number of PRBS words, so every
                    # captured beat is a full word_bytes.
                    if n >= 2:
                        if upper_nz:
                            passed = False
                            fail_reason = f"frame {fi} beat {n}: upper bytes not zero (lane swap!)"
                            continue
                        if prev is not None and low32 != prev + 1:
                            passed = False
                            fail_reason = (f"frame {fi} beat {n}: counter not +1 "
                                           f"({prev} -> {low32})")
                            continue
                        prev = low32

            # Restore PRBS mode (the PRBS path runs next)
            prbs.FwCnt.set(False)

            print(
                "--- counter-mode byte-order result ---\n"
                f"  Frames captured        : {len(cap.frames)} (target {args.target})\n"
                f"  Dma.SuccessCounter     : {dma.SuccessCounter.get()}\n"
                f"  Beat layout            : {word_bytes}B/beat, beat0=seed beat1=len then +1 ramp\n"
                "  Beat dump:\n" + "\n".join(dump_lines) + "\n"
                f"  Failure                : {fail_reason if fail_reason else '(none)'}\n"
                f"  RESULT                 : {'PASS' if passed else 'FAIL'}\n"
                "--------------------------------------"
            )
            sys.exit(0 if passed else 1)

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
