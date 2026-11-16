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

import surf.protocols.ssi as ssi

import simple_10gbe_rudp_kcu105_example as devBoard

class App(pr.Device):
    def __init__( self,sim=False,**kwargs):
        super().__init__(**kwargs)

        # FW PRBS transmitter (FW -> SW on the RUDP[1] stream)
        # clock_freq only scales the TrigRate display (1GbE builds run at 125 MHz)
        self.add(ssi.SsiPrbsTx(
            offset     = 0x0000_0000,
            clock_freq = 156.25e6,
            expand     = True,
        ))

        self.add(devBoard.AppMem(
            offset  = 0x0001_0000,
        ))

        # FW PRBS receiver (SW -> FW on the RUDP[1] stream)
        self.add(ssi.SsiPrbsRx(
            offset      = 0x0004_0000,
            seedBits    = 64,
            rxClkPeriod = 6.4e-9,
            expand      = True,
        ))
