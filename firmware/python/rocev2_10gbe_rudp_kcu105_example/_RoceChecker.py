#-----------------------------------------------------------------------------
# This file is part of the 'Simple-10GbE-RUDP-KCU105-Example'. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the 'Simple-10GbE-RUDP-KCU105-Example', including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------

import pyrogue as pr

class RoceChecker(pr.Device):
    def __init__( self,
                  dispatchBits=24,
                  **kwargs):
        super().__init__(**kwargs)

        self.add(pr.RemoteVariable(
            name         = 'SuccessCounter',
            offset       = 0xF00,
            bitSize      = dispatchBits,
            mode         = 'RO',
        ))

        self.add(pr.RemoteVariable(
            name         = 'UnsuccessCounter',
            offset       = 0xF04,
            bitSize      = dispatchBits,
            mode         = 'RO',
        ))

        self.add(pr.RemoteVariable(
            name         = 'ResetCounters',
            offset       = 0xF08,
            bitSize      = 1,
            mode         = 'WO',
        ))
