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
"""
fileReader.py — Read rogue .dat files written by StreamWriter.

Extends the upstream fileReader with:
  - --channel  : filter by rogue stream channel
                 (channel 0 = UDP/RSSI stream, channel 1 = RoCEv2 RDMA stream)
  - --check-cont : verify the payload bytes are contiguous across frames
                   (i.e. each frame starts where the previous one ended,
                   using an incrementing 0x00..0xff byte pattern)
  - --hex      : hex dump each frame payload
  - --debug    : enable SwRx DebugPrint (prints header word of each frame)

Usage:
    # Read all frames, print summary
    python3 fileReader.py --dataFile data.dat

    # Check RoCEv2 frames (channel 1) for contiguous byte pattern
    python3 fileReader.py --dataFile data.dat --channel 1 --check-cont

    # Hex dump UDP frames (channel 0)
    python3 fileReader.py --dataFile data.dat --channel 0 --hex

    # Enable upstream SwRx debug print
    python3 fileReader.py --dataFile data.dat --debug
"""
import setupLibPaths

import pyrogue as pr
import rogue.utilities.fileio
import rogue.interfaces.stream as ris
import argparse
import numpy as np

import simple_10gbe_rudp_kcu105_example as devBoard


# ---------------------------------------------------------------------------
# Contiguity-checking stream slave
# ---------------------------------------------------------------------------
class ContiguityChecker(ris.Slave):
    """
    Stream slave that checks received frames for a contiguous incrementing
    byte pattern (0x00 0x01 ... 0xff 0x00 ...) across frame boundaries.

    Connect downstream of a channel filter so it only sees the frames
    you care about.
    """
    def __init__(self, channel=None):
        super().__init__()
        self._channel    = channel
        self._last_byte  = None
        self._frame_num  = 0
        self._gap_count  = 0
        self._byte_count = 0

    def _acceptFrame(self, frame):
        # Read payload
        size     = frame.getPayload()
        buf      = bytearray(size)
        frame.read(buf, 0)

        self._frame_num  += 1
        self._byte_count += size

        ch_str = f'ch{self._channel} ' if self._channel is not None else ''
        print(
            f'Frame {self._frame_num:>6d} | '
            f'{ch_str}'
            f'size={size:>8d} bytes'
        )

        if size == 0:
            return

        first_byte = buf[0]

        if self._last_byte is not None:
            expected = (self._last_byte + 1) % 256
            if first_byte != expected:
                self._gap_count += 1
                print(
                    f'  *** GAP at frame {self._frame_num}: '
                    f'expected 0x{expected:02x} got 0x{first_byte:02x} '
                    f'(delta={(first_byte - expected) % 256})'
                )

        self._last_byte = buf[-1]

    def summary(self):
        print()
        print(
            f'Total: {self._frame_num} frame(s), '
            f'{self._byte_count} bytes '
            f'({self._byte_count / 1024:.1f} KB)'
        )
        if self._gap_count == 0:
            print('Contiguity: OK — no gaps detected')
        else:
            print(f'Contiguity: FAIL — {self._gap_count} gap(s) detected')


# ---------------------------------------------------------------------------
# Hex-dumping stream slave
# ---------------------------------------------------------------------------
class HexDumper(ris.Slave):
    """Stream slave that hex-dumps each received frame."""

    def __init__(self, bytes_per_row=16):
        super().__init__()
        self._bytes_per_row = bytes_per_row
        self._frame_num     = 0

    def _acceptFrame(self, frame):
        size = frame.getPayload()
        buf  = bytearray(size)
        frame.read(buf, 0)
        self._frame_num += 1
        print(f'--- Frame {self._frame_num} ({size} bytes) ---')
        bpr = self._bytes_per_row
        for i in range(0, size, bpr):
            chunk  = buf[i:i + bpr]
            hex_   = ' '.join(f'{b:02x}' for b in chunk)
            ascii_ = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            print(f'  {i:08x}:  {hex_:<{bpr * 3}}  {ascii_}')
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description='Read rogue .dat files with optional contiguity check')

    parser.add_argument(
        "--dataFile",
        type     = str,
        required = True,
        help     = "Path to .dat file written by StreamWriter",
    )
    parser.add_argument(
        "--channel",
        type    = int,
        default = None,
        help    = "Filter by rogue stream channel. "
                  "0 = UDP/RSSI stream, 1 = RoCEv2 RDMA stream. "
                  "Default: show all channels",
    )
    parser.add_argument(
        "--check-cont",
        action  = 'store_true',
        help    = "Check that frame payloads form a contiguous incrementing "
                  "byte pattern across frame boundaries",
    )
    parser.add_argument(
        "--hex",
        action  = 'store_true',
        help    = "Hex dump each frame payload",
    )
    parser.add_argument(
        "--debug",
        action  = 'store_true',
        help    = "Enable SwRx DebugPrint (prints header word of each frame)",
    )

    args = parser.parse_args()

    #################################################################

    # File reader
    dataReader = rogue.utilities.fileio.StreamReader()

    # pyrogue root with upstream SwRx
    root = pr.Root()
    root.add(devBoard.SwRx())
    root.start()

    if args.debug:
        root.SwRx.DebugPrint.setDisp(True)

    # Wire: file reader → SwRx (upstream behaviour, always present)
    dataReader >> root.SwRx

    # Optional channel filter + contiguity checker / hex dumper
    checkers = []

    if args.check_cont or args.hex:
        if args.channel is not None:
            # Filter to the requested channel then attach checker/dumper
            filt = ris.Filter(False, args.channel)
            dataReader >> filt

            if args.check_cont:
                checker = ContiguityChecker(channel=args.channel)
                filt >> checker
                checkers.append(checker)

            if args.hex:
                dumper = HexDumper()
                filt >> dumper

        else:
            # No channel filter — attach directly
            if args.check_cont:
                checker = ContiguityChecker()
                dataReader >> checker
                checkers.append(checker)

            if args.hex:
                dumper = HexDumper()
                dataReader >> dumper

    # Open and process the file
    dataReader.open(args.dataFile)
    dataReader.closeWait()

    root.stop()

    # Print contiguity summary
    for c in checkers:
        c.summary()
