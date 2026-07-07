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
# Standalone PyRogue driver for the RogueTcpStreamWrap loopback demo
# (firmware/targets/Simple10GbeRudpKcu105Example/tb/RogueTcpStreamXsimDemoTb.vhd).
#
# This script runs as a SEPARATE OS process from the Vivado xsim GUI. Start
# the xsim simulation FIRST -- the demo TB must already be running and bound
# to PORT_NUM below (via the RogueTcpStreamWrap DPI core) -- then run this
# script. Connecting before the simulator has bound the port will fail the
# TCP handshake. Never run this driver on the simulator's own thread or
# process; a blocking recv there would freeze the Vivado GUI.
#-----------------------------------------------------------------------------
import argparse
import time

import pyrogue as pr
import rogue.interfaces.stream as ris
from pyrogue.utilities.prbs import PrbsTx, PrbsRx

# Must match PORT_NUM_C in RogueTcpStreamXsimDemoTb.vhd
PORT_NUM = 9000


class PrbsLoopbackRoot(pr.Root):
    def __init__(self, **kwargs):
        super().__init__(
            name        = 'PrbsLoopbackRoot',
            description = 'PRBS loopback demo through RogueTcpStreamWrap',
            **kwargs)

        # A single shared TcpClient wires both directions: PrbsTx pushes
        # frames out through the client's Slave interface, PrbsRx receives
        # the looped-back frames through the client's Master interface.
        self.tcp = ris.TcpClient("127.0.0.1", PORT_NUM)

        self.add(PrbsTx(name='PrbsTx', stream=self.tcp))
        self.add(PrbsRx(name='PrbsRx', stream=self.tcp))


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--frameCount",
        type     = int,
        required = False,
        default  = 10,
        help     = "Number of PRBS frames to generate in the bounded burst",
    )

    parser.add_argument(
        "--frameSize",
        type     = int,
        required = False,
        default  = 1024,
        help     = "PRBS frame size in bytes",
    )

    parser.add_argument(
        "--timeout",
        type     = float,
        required = False,
        default  = 5.0,
        help     = "Seconds to wait for the loopback frames to arrive before reading rxErrors",
    )

    args = parser.parse_args()

    with PrbsLoopbackRoot() as root:

        root.PrbsTx.txSize.set(args.frameSize)

        print('###################################################')
        print('#     PRBS loopback demo through RogueTcpStream    #')
        print('###################################################')
        print(f'Driving {args.frameCount} PRBS frame(s) of {args.frameSize} byte(s) '
              f'through RogueTcpStreamWrap on 127.0.0.1:{PORT_NUM} ...')

        # Bounded one-shot burst -- not a free-running txPeriod stream
        root.PrbsTx.genFrame(args.frameCount)

        # Give the loopback path time to drain before reading the oracle
        time.sleep(args.timeout)

        rxCount  = root.PrbsRx.rxCount.get()
        rxErrors = root.PrbsRx.rxErrors.get()

        print(f'PrbsRx.rxCount  = {rxCount}')
        print(f'PrbsRx.rxErrors = {rxErrors}')

        if rxErrors == 0:
            print('PASS: rxErrors == 0 -- DPI marshalling is byte-correct')
        else:
            print('FAIL: rxErrors != 0 -- see Pitfall 1 (silent DPI payload corruption)')

        print('###################################################')
