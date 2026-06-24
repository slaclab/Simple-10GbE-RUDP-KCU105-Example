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
# Headless probe for the "sticky half-bandwidth after backpressure clears" bug.
#
# Drives the exact operator sequence (no PyDM GUI) and samples FW telemetry at
# each step, reporting the SuccessCounter COMPLETION RATE (deltas/sec) alongside
# the AxiStreamMon bandwidth. The decisive question this answers:
#
#   * If SuccessCounter rate halves at the stuck-half point  -> SQ completes
#     SENDs at half rate -> blue-rdma SQ retry latch (expected).
#   * If SuccessCounter rate is ~unchanged but bandwidth halves -> each SEND
#     carries half goodput -> SLAC core SERVE/FILL framing/replay-length bug.
#
# Steady-state sampling helper: takes two SuccessCounter snapshots dt apart and
# reports the per-second completion rate, plus the live MonBandwidth (Mbps) and
# DCQCN telemetry (Rc/Rt/CnpCounter) to confirm DCQCN is bypassed (Rc pinned).
#-----------------------------------------------------------------------------
import setupLibPaths          # MUST be first — adds firmware/python + surf/python to sys.path

import time
import argparse

import pyrogue

import rocev2_10gbe_rudp_kcu105_example as roceBoard

LINE_RATE_BPS = 1250000000   # 10 Gb/s in Byte/s — Rc pinned here under DcqcnBypass


def sample(prbs, dma, dcqcn, mon, dt=1.0):
    """Snapshot telemetry; measure SuccessCounter completion rate over dt seconds."""
    s0 = dma.SuccessCounter.get(read=True)
    u0 = dma.UnsuccessCounter.get(read=True)
    d0 = dma.DmaReadCount.get(read=True)
    t0 = time.monotonic()
    time.sleep(dt)
    s1 = dma.SuccessCounter.get(read=True)
    u1 = dma.UnsuccessCounter.get(read=True)
    d1 = dma.DmaReadCount.get(read=True)
    t1 = time.monotonic()
    dt_real = t1 - t0

    succ_rate = (s1 - s0) / dt_real
    dma_rate  = (d1 - d0) / dt_real
    return {
        'trigDly'     : prbs.TrigDly.get(read=True),
        'bw_mbps'     : mon.Bandwidth.get(read=True),
        'succ_rate'   : succ_rate,
        'dma_rate'    : dma_rate,
        'tx_per_comp' : (dma_rate / succ_rate) if succ_rate > 0 else 0.0,
        'unsucc_rate' : (u1 - u0) / dt_real,
        'succ_total'  : s1,
        'unsucc_total': u1,
        'oversize'    : dma.OversizeCount.get(read=True),
        'monFrameRate': dma.MonFrameRate.get(read=True),
        'monFrameSize': dma.MonFrameSize.get(read=True),
        'rc'          : dcqcn.Rc.get(read=True),
        'rt'          : dcqcn.Rt.get(read=True),
        'cnp'         : dcqcn.CnpCounter.get(read=True),
    }


def show(label, s):
    print(
        f"[{label:<28}] TrigDly={s['trigDly']:<10} "
        f"Mon.Bandwidth={s['bw_mbps']:9.1f} Mbps | "
        f"Succ rate={s['succ_rate']:9.1f}/s (tot {s['succ_total']}) "
        f"DmaRead rate={s['dma_rate']:9.1f}/s  TX/comp={s['tx_per_comp']:.2f} | "
        f"Unsucc rate={s['unsucc_rate']:6.1f}/s (tot {s['unsucc_total']}) "
        f"oversize={s['oversize']} | "
        f"MonFrameRate={s['monFrameRate']} Hz MonFrameSize={s['monFrameSize']} B | "
        f"Rc={s['rc']} Rt={s['rt']} Cnp={s['cnp']}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Headless probe for the RoCEv2 sticky-half bandwidth bug')
    parser.add_argument("--ip",       type=str,   default='192.168.2.10')
    parser.add_argument("--trigRate", type=float, default=2.5e4,
                        help="throttled-phase PRBS rate (Hz); full rate uses TrigDly=0")
    parser.add_argument("--settle",   type=float, default=3.0,
                        help="seconds to let each step settle before sampling")
    parser.add_argument("--dt",       type=float, default=2.0,
                        help="seconds between the two SuccessCounter snapshots")
    parser.add_argument("--roceDevice", type=str, default='mlx5_0')
    parser.add_argument("--roceGidIndex", type=int, default=None)
    args = parser.parse_args()

    gidIndex = args.roceGidIndex if args.roceGidIndex is not None else -1

    rocev2Cfg = pyrogue.protocols.RoCEv2ServerCfg(
        ip         = args.ip,
        deviceName = args.roceDevice,
        gidIndex   = gidIndex,
    )
    transportCfg = pyrogue.protocols.RoCEv2TransportCfg(minRnrTimer=1)  # p2p default

    with roceBoard.Root(
        rocev2Cfg    = rocev2Cfg,
        transportCfg = transportCfg,
        p2p          = True,
        pollEn       = True,
        initRead     = True,
        zmqSrvPort   = 0,
    ) as root:

        rx          = root.rdmaRx
        prbs        = root.App.SsiPrbsTx
        dma         = root.Core.RoCEv2AxiStreamRdma.Core
        dcqcn       = root.Core.RoCEv2AxiStreamRdma.Dcqcn
        mon         = root.App.RdmaAxisMon.Ch[0]

        max_payload = rx.MaxPayload.get()
        word_bytes  = prbs.WordSize.get() // 8
        remQpn      = rx.HostQpn.get()
        locKey      = rx.FpgaLkey.get()
        rxQDepth    = rx.RxQueueDepth.get()

        prbs.PacketLength.set(max_payload // word_bytes - 1)
        dma.LKey.set(locKey)
        dma.SQpn.set(remQpn)
        dma.AddrWrapCount.set((rxQDepth * max_payload) // max_payload)

        dma.ResetCounters()
        root.CountReset()

        # ----------------------------------------------------------------
        # Arm the stream. Flow control is native FW<->NIC RNR.
        # ----------------------------------------------------------------
        dma.DispatchEnable.set(True)
        prbs.TxEn.set(True)

        print("\n=== RoCEv2 sticky-half probe — driving the operator sequence ===")
        print(f"settle={args.settle}s  rate-window dt={args.dt}s  trigRate={args.trigRate} Hz\n")

        # Step A: throttled, SW payload check ON (baseline backpressure)
        prbs.TrigRate.set(args.trigRate)
        root.PrbsRx.checkPayload.set(True)
        time.sleep(args.settle)
        show("throttled + SW-on", sample(prbs, dma, dcqcn, mon, args.dt))

        # Step B: throttled, SW payload check OFF
        root.PrbsRx.checkPayload.set(False)
        time.sleep(args.settle)
        show("throttled + SW-off", sample(prbs, dma, dcqcn, mon, args.dt))

        # Step C: full rate, SW OFF -> expect line rate (~9752 Mbps)
        prbs.TrigDly.set(0)
        time.sleep(args.settle)
        show("fullrate + SW-off (REF)", sample(prbs, dma, dcqcn, mon, args.dt))

        # Step D: full rate, SW ON -> heavy backpressure (expected low)
        root.PrbsRx.checkPayload.set(True)
        time.sleep(args.settle)
        show("fullrate + SW-on", sample(prbs, dma, dcqcn, mon, args.dt))

        # Step E: full rate, SW OFF -> THE BUG: expect stuck ~half, never recovers
        root.PrbsRx.checkPayload.set(False)
        time.sleep(args.settle)
        stuck = sample(prbs, dma, dcqcn, mon, args.dt)
        show("fullrate + SW-off (STUCK?)", stuck)

        # Step E': hold and re-sample to confirm it stays stuck (not transient ramp)
        time.sleep(args.settle)
        show("fullrate + SW-off (HOLD)", sample(prbs, dma, dcqcn, mon, args.dt))

        # Step F: TxEn drain workaround -> expect recovery to line rate
        prbs.TxEn.set(False)
        time.sleep(1.0)
        prbs.TxEn.set(True)
        time.sleep(args.settle)
        show("fullrate + SW-off (TxEn drain)", sample(prbs, dma, dcqcn, mon, args.dt))

        # ----------------------------------------------------------------
        # Decision branch summary
        # ----------------------------------------------------------------
        ref_succ = None  # captured below from the printed REF if desired
        print("\n=== DECISION BRANCH ===")
        print("Compare 'fullrate + SW-off (REF)' vs 'STUCK?'/'HOLD':")
        print("  * Succ rate halves      -> SQ completes SENDs at half rate -> blue-rdma retry latch.")
        print("  * Succ rate ~unchanged, -> each SEND carries half goodput  -> SLAC core SERVE/FILL.")
        print("    bandwidth halves")
        print(f"  Rc at stuck point = {stuck['rc']} (expect {LINE_RATE_BPS} if DCQCN bypassed),"
              f" Cnp={stuck['cnp']} (expect flat)")

        dma.DispatchEnable.set(False)
        prbs.TxEn.set(False)

    print("\nProbe complete.")
