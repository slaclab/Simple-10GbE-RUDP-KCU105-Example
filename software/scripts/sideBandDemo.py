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
#
# Standalone raw-pyzmq driver for the RogueSideBandWrap bidirectional demo
# (firmware/targets/Simple10GbeRudpKcu105Example/tb/RogueSideBandXsimDemoTb.vhd).
#
# This script runs as a SEPARATE OS process from the Vivado xsim GUI. Start
# the xsim simulation FIRST -- the demo TB must already be running and bound
# to PORT_NUM below (via the RogueSideBandWrap DPI core) -- then run this
# script. Connecting before the simulator has bound the port will fail the
# TCP handshake. Never run this driver on the simulator's own thread or
# process; a blocking recv there would freeze the Vivado GUI.
#
# Unlike the Stream/Memory demos, this driver has no PyRogue Root: surf
# exposes side-band only as PGP register fields, so there is no high-level
# PyRogue client to model on. It speaks the raw 4-byte
# [opCodeEn, opCode, remDataChanged, remData] wire protocol directly over
# pyzmq, mirroring the surf cocotb regression's side-band peer helper.
#-----------------------------------------------------------------------------
import argparse

import zmq

# Must match PORT_NUM_C in RogueSideBandXsimDemoTb.vhd
PORT_NUM = 9200

# Must match TX_OPCODE_C / TX_REMDATA_C in RogueSideBandXsimDemoTb.vhd
TX_OPCODE_EXPECTED  = 0x3C
TX_REMDATA_EXPECTED = 0x81

RCVTIMEO_MS = 5000


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--timeout",
        type     = int,
        required = False,
        default  = RCVTIMEO_MS,
        help     = "Milliseconds to wait for the TB's tx stimulus frame before giving up",
    )

    args = parser.parse_args()

    ctx  = zmq.Context()
    push = ctx.socket(zmq.PUSH)   # -> DUT's PULL (port+1)
    pull = ctx.socket(zmq.PULL)   # <- DUT's PUSH (port)
    pull.setsockopt(zmq.RCVTIMEO, args.timeout)

    # RogueSideBandRestart binds PULL on port+1, PUSH on port; this driver
    # connects the opposite way, as a client: PUSH -> port+1 feeds the DUT's
    # PULL, PULL <- port drains the DUT's PUSH. Inverting these silently
    # hangs both sides on RCVTIMEO.
    push.connect(f"tcp://127.0.0.1:{PORT_NUM + 1}")
    pull.connect(f"tcp://127.0.0.1:{PORT_NUM}")

    print('###################################################')
    print('#  Bidirectional opcode/remData demo through RogueSideBand  #')
    print('###################################################')
    print(f'Connecting to RogueSideBandWrap on 127.0.0.1:{PORT_NUM} ...')

    # rx direction: send an rx* frame the DUT should surface on
    # rxOpCode/rxOpCodeEn/rxRemData -- [opCodeEn, opCode, remDataChanged, remData]
    rxOpCode  = 0x5A
    rxRemData = 0xA5
    push.send(bytes([1, rxOpCode, 1, rxRemData]))
    print(f'Sent rx frame: opCode=0x{rxOpCode:02x}, remData=0x{rxRemData:02x} '
          f'-- check the waveform for the rxOpCodeEn pulse and rxOpCode/rxRemData latch')

    # tx direction: receive + assert the DUT's tx* stimulus frame (driven by
    # the demo TB's stimulus process)
    try:
        msg = pull.recv()
    except zmq.error.Again:
        print('FAIL: TIMED OUT waiting for tx stimulus frame from the demo TB')
        raise SystemExit(1)

    opCodeEn, opCode, remDataChanged, remData = msg[0], msg[1], msg[2], msg[3]

    print(f'Received tx frame: opCodeEn={opCodeEn}, opCode=0x{opCode:02x}, '
          f'remDataChanged={remDataChanged}, remData=0x{remData:02x}')

    if opCodeEn == 1 and opCode == TX_OPCODE_EXPECTED and remData == TX_REMDATA_EXPECTED:
        print('PASS: bidirectional opcode/remData marshalling verified')
    else:
        print(f'FAIL: tx mismatch, got {msg!r}')

    print('###################################################')
