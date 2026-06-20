#-----------------------------------------------------------------------------
# This file is part of the 'Simple-10GbE-RUDP-KCU105-Example'. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the 'Simple-10GbE-RUDP-KCU105-Example', including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------

import surf.protocols.ssi as ssi

import pyrogue  as pr
import simple_10gbe_rudp_kcu105_example as baseBoard

# class App(baseBoard.App):
class App(pr.Device):
    def __init__( self, **kwargs):
        super().__init__(**kwargs)

        self.add(ssi.SsiPrbsTx(
            offset     = 0x0002_0000,
            clock_freq = 156.25e6,
            expand     = True,
        ))
