#-----------------------------------------------------------------------------
# This file is part of the 'Simple-10GbE-RUDP-KCU105-Example'. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#     https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the 'Simple-10GbE-RUDP-KCU105-Example', including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------

import pyrogue as pr

import simple_10gbe_rudp_kcu105_example as devBoard

import surf.protocols.pgp as pgp
import surf.protocols.ssi as ssi

class App(pr.Device):
    def __init__( self,sim=False,**kwargs):
        super().__init__(**kwargs)

        self.add(devBoard.AppTx(
            offset = 0x0000_0000,
            expand = True,
        ))

        self.add(devBoard.AppMem(
            offset  = 0x0001_0000,
        ))

        for i in range(4):
            self.add(pgp.Pgp4AxiL(
                name    = f"Pgp4AxiL[{i}]",
                offset  = 0x0002_0000 + (i * 0x2000), # 8kB stride
                numVc   = 1,
                writeEn = True,
                enabled = True,
            ))
            
            self.add(ssi.SsiPrbsTx(
                name   = f"PrbsTx[{i}]",
                offset = 0x0003_0000 + (i * 0x1000), # 4kB stride
                expand = True,
            ))

            self.add(ssi.SsiPrbsRx(
                name   = f"PrbsRx[{i}]",
                offset = 0x0003_4000 + (i * 0x1000), # 4kB stride
                expand = True,
            ))
        
        
