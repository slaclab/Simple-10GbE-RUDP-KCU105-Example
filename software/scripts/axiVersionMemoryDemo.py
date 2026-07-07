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
# Standalone PyRogue driver for the RogueTcpMemoryWrap AxiVersion demo
# (firmware/targets/Simple10GbeRudpKcu105Example/tb/RogueTcpMemoryXsimDemoTb.vhd).
#
# This script runs as a SEPARATE OS process from the Vivado xsim GUI. Start
# the xsim simulation FIRST -- the demo TB must already be running and bound
# to PORT_NUM below (via the RogueTcpMemoryWrap DPI core) -- then run this
# script. Connecting before the simulator has bound the port will fail the
# TCP handshake. Never run this driver on the simulator's own thread or
# process; a blocking recv there would freeze the Vivado GUI.
#-----------------------------------------------------------------------------
import argparse

import pyrogue as pr
import rogue.interfaces.memory as rim
import surf.axi as axi

# Must match PORT_NUM_C in RogueTcpMemoryXsimDemoTb.vhd
PORT_NUM = 9100


class AxiVersionMemoryRoot(pr.Root):
    def __init__(self, **kwargs):
        super().__init__(
            name        = 'AxiVersionMemoryRoot',
            description = 'AxiVersion ScratchPad demo through RogueTcpMemoryWrap',
            **kwargs)

        # DPI-C core is the ZMQ server; this script connects as the client.
        self.tcp = rim.TcpClient("127.0.0.1", PORT_NUM)

        self.add(axi.AxiVersion(name='AxiVersion', memBase=self.tcp))


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--testVal",
        type     = lambda x: int(x, 0),
        required = False,
        default  = 0xDEADBEEF,
        help     = "32-bit value to write to AxiVersion.ScratchPad for the readback oracle",
    )

    args = parser.parse_args()

    with AxiVersionMemoryRoot() as root:

        print('###################################################')
        print('#  AxiVersion ScratchPad demo through RogueTcpMemory  #')
        print('###################################################')
        print(f'Connecting to RogueTcpMemoryWrap on 127.0.0.1:{PORT_NUM} ...')

        root.AxiVersion.ScratchPad.set(args.testVal)
        readback = root.AxiVersion.ScratchPad.get()

        buildStamp = root.AxiVersion.BuildStamp.get()
        gitHash    = root.AxiVersion.GitHash.get()

        print(f'Wrote     0x{args.testVal:08x}')
        print(f'Readback  0x{readback:08x}')
        print(f'BuildStamp = {buildStamp!r}')
        print(f'GitHash    = {gitHash:#042x}')

        if readback == args.testVal:
            print('PASS: ScratchPad readback matches -- DPI marshalling is byte-correct')
        else:
            print(f'FAIL: wrote 0x{args.testVal:08x}, read back 0x{readback:08x}')

        print('###################################################')
