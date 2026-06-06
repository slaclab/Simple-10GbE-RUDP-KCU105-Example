#-----------------------------------------------------------------------------
# This file is part of the 'Simple-10GbE-RUDP-KCU105-Example'. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the 'Simple-10GbE-RUDP-KCU105-Example', including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------

import simple_10gbe_rudp_kcu105_example as baseBoard
import rocev2_10gbe_rudp_kcu105_example as roceBoard

class App(baseBoard.App):
    def __init__( self, dispatchBits=24, **kwargs):
        super().__init__(**kwargs)

        self.add(roceBoard.RoceDispatcher(
            offset       = 0x0002_0000,
            dispatchBits = dispatchBits,
            expand       = False,
        ))

        self.add(roceBoard.RoceChecker(
            offset       = 0x0003_0000,
            dispatchBits = dispatchBits,
            expand       = False,
        ))
