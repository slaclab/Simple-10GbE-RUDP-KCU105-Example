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

class AppMem(pr.Device):
    def __init__( self,**kwargs):
        super().__init__(**kwargs)

        self.add(pr.RemoteVariable(
            name         = "DataBlock",
            description  = "",
            offset       = 0,
            bitSize      = 32 * 0x100,
            bitOffset    = 0,
            numValues    = 0x100,
            valueBits    = 32,
            valueStride  = 32,
            updateNotify = True,
            bulkOpEn     = True,
            overlapEn    = True,
            verify       = True,
            hidden       = True,
            base         = pr.UInt,
            mode         = "RW",
        ))