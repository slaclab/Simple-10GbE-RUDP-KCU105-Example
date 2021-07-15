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

import sys
import argparse
import glob
import time
from collections import OrderedDict as odict

import pyrogue as pr
import pyrogue.pydm

import simple_10gbe_rudp_kcu105_example as devBoard

#################################################################

if __name__ == "__main__":

    # Convert str to bool
    argBool = lambda s: s.lower() in ['true', 't', 'yes', '1']

    # Set the argument parser
    parser = argparse.ArgumentParser()

    # Add arguments
    parser.add_argument(
        "--ip",
        type     = str,
        required = False,
        default  = '192.168.2.10',
        help     = "IP address",
    )

    parser.add_argument(
        "--path",
        type     = str,
        default  = None,
        required = False,
        help     = "path to images",
    )

    # Get the arguments
    args = parser.parse_args()

    #################################################################

    with devBoard.Root(
        ip       = args.ip,
        pollEn   = False,
        initRead = True,
        promProg = True,
    ) as root:

        # Create useful pointers
        AxiVersion = root.Core.AxiVersion
        PROM_PRI   = root.Core.AxiMicronN25Q[0]
        PROM_SEC   = root.Core.AxiMicronN25Q[1]

        # Printout Current AxiVersion status
        print ( '###################################################')
        print ( '#                 Old Firmware                    #')
        print ( '###################################################')
        AxiVersion.printStatus()

        # Get a list of images, using .mcs first
        imgLst = odict()

        rawLst = glob.glob('{}/*.mcs*'.format(args.path))
        for l in rawLst:

            # Determine suffix
            if '.mcs.gz' in l:
                suff = 'mcs.gz'
            else:
                suff = 'mcs'

            # Get basename
            l = l.replace('_primary.mcs.gz','')
            l = l.replace('_secondary.mcs.gz','')
            l = l.replace('_primary.mcs','')
            l = l.replace('_secondary.mcs','')
            l = l.replace('.mcs.gz','')
            l = l.replace('.mcs','')

            # Store entry
            imgLst[l] = suff

        # Sort list
        imgLst = odict(sorted(imgLst.items(), key=lambda x: x[0]))

        for i,l in enumerate(imgLst.items()):
            print('{} : {}'.format(i,l[0]))

        idx = int(input('Enter image to program into the PCIe card\'s PROM: '))

        ent = list(imgLst.items())[idx]
        pri = ent[0] + '_primary.' + ent[1]
        sec = ent[0] + '_secondary.' + ent[1]

        # Load the primary MCS file
        PROM_PRI.LoadMcsFile(pri)

        # Check if the primary MCS failed
        if PROM_PRI._progDone:
            # Load the secondary MCS file
            PROM_SEC.LoadMcsFile(sec)
        else:
            print('Failed to program FPGA')

        # Update the programing done flag
        progDone = PROM_PRI._progDone and PROM_SEC._progDone

        # Check if programming was successful
        if (progDone):
            print('\nReloading FPGA firmware from PROM ....')
            AxiVersion.FpgaReload()
            time.sleep(5)
            print('\nReloading FPGA done')

            print ( '###################################################')
            print ( '#                 New Firmware                    #')
            print ( '###################################################')
            AxiVersion.printStatus()
        else:
            print('Failed to program FPGA')

    #################################################################
