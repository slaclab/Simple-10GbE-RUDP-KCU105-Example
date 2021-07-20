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

import argparse

import pyrogue.pydm

#################################################################

if __name__ == "__main__":

    # Convert str to bool
    argBool = lambda s: s.lower() in ['true', 't', 'yes', '1']

    # Set the argument parser
    parser = argparse.ArgumentParser()

    # Add arguments
    parser.add_argument(
        "--serverList",
        type     = str,
        required = False,
        default  = 'localhost:9099',
        help     = "IP address",
    )

    # Get the arguments
    args = parser.parse_args()

    ###########################################################################################
    # Refer to https://github.com/slaclab/rogue/blob/master/python/pyrogue/pydm/__init__.py#L17
    ###########################################################################################
    pyrogue.pydm.runPyDM(serverList='localhost:9099')

    #################################################################
