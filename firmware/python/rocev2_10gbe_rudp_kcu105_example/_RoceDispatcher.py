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

class RoceDispatcher(pr.Device):
    def __init__( self,
                  dispatchBits=24,
                  **kwargs):
        super().__init__(**kwargs)

        self.add(pr.RemoteVariable(
            name         = 'StartDispatching',
            offset       = 0xF00,
            bitSize      = 1,
            mode         = 'RW',
        ))

        self.add(pr.RemoteVariable(
            name         = 'DispatchCounter',
            offset       = 0xF00,
            bitSize      = dispatchBits,
            bitOffset    = 1,
            disp         = '{:d}',
            mode         = 'RW',
        ))

        self.add(pr.RemoteVariable(
            name         = 'Len',
            offset       = 0xF04,
            bitSize      = 32,
            disp         = '{:d}',
            mode         = 'RW',
        ))

        self.add(pr.RemoteVariable(
            name         = 'RKey',
            offset       = 0xF08,
            bitSize      = 32,
            mode         = 'RW',
        ))

        self.add(pr.RemoteVariable(
            name         = 'LKey',
            offset       = 0xF0C,
            bitSize      = 32,
            mode         = 'RW',
        ))

        self.add(pr.RemoteVariable(
            name         = 'SQpn',
            offset       = 0xF10,
            bitSize      = 24,
            mode         = 'RW',
        ))

        self.add(pr.RemoteVariable(
            name         = 'DQpn',
            offset       = 0xF14,
            bitSize      = 24,
            mode         = 'RW',
        ))

        self.add(pr.RemoteVariable(
            name         = 'RemAddr',
            offset       = 0xF18,
            bitSize      = 64,
            mode         = 'RW',
        ))

        self.add(pr.RemoteVariable(
            name         = 'AddrWrapCount',
            offset       = 0xF20,
            bitSize      = 32,
            mode         = 'RW',
        ))
