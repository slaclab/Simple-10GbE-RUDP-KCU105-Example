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
import setupLibPaths

import pyrogue as pr

import rogue.utilities.fileio

import argparse

import pyrogue.utilities.prbs

if __name__ == "__main__":

    #################################################################

    # Set the argument parser
    parser = argparse.ArgumentParser()

    # Add arguments
    parser.add_argument(
        "--dataFile",
        type     = str,
        required = True,
        help     = "path to data file",
    )

    # Get the arguments
    args = parser.parse_args()

    #################################################################

    # Create the File reader streaming interface
    dataReader = rogue.utilities.fileio.StreamReader()

    # Create the software PRBS receiver to check the recorded frames
    root = pr.Root()
    root.add(pr.utilities.prbs.PrbsRx(
        name         = 'SwPrbsRx',
        width        = 64,
        checkPayload = True,
    ))
    root.start()

    # Connect the file reader ---> root.SwPrbsRx
    dataReader >> root.SwPrbsRx

    # Open the file
    dataReader.open(args.dataFile)

    # Close file once everything processed
    dataReader.closeWait()

    # Print the PRBS receiver results
    print( f'rxCount  = {root.SwPrbsRx.rxCount.get()}' )
    print( f'rxBytes  = {root.SwPrbsRx.rxBytes.get()}' )
    print( f'rxErrors = {root.SwPrbsRx.rxErrors.get()}' )
    root.stop()

    #################################################################
