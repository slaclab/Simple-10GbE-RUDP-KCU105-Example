#-----------------------------------------------------------------------------
# This file is part of the 'Development Board Examples'. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the 'Development Board Examples', including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------

import pyrogue  as pr
import pyrogue.protocols

import simple_10gbe_rudp_kcu105_example as devBoard

import rogue
import rogue.hardware.axi
import rogue.interfaces.stream

class Root(pr.Root):
    def __init__(   self,
            ip       = '192.168.2.10',
            pollEn   = True,  # Enable automatic polling registers
            initRead = True,  # Read all registers at start of the system
            **kwargs):

        #################################################################

        self.sim = (ip == 'sim')
        if (self.sim):
            # Set the timeout
            kwargs['timeout'] = 100000000 # firmware simulation slow and timeout base on real time (not simulation time)

        else:
            # Set the timeout
            kwargs['timeout'] = 5000000 # 5.0 seconds default

        super().__init__(**kwargs)

        #################################################################

        if (not self.sim):

            # Start up flags
            self._pollEn   = pollEn
            self._initRead = initRead

            # Add RUDP Software clients
            self.rudp = [None for i in range(2)]

            # for i in range(1):
            for i in range(2):
                # Create the ETH interface @ IP Address = ip
                self.rudp[i] = pr.protocols.UdpRssiPack(
                    name    = f'SwRudpClient[{i}]',
                    host    = ip,
                    port    = 8192+i,
                    packVer = 2,
                    jumbo   = (i>0), # Jumbo frames for RUDP[1] (streaming) only
                    expand  = False,
                    )
                self.add(self.rudp[i])

            # Map the RDUP streams
            self.RudpReg = self.rudp[0].application(0)
            self.stream  = self.rudp[1].application(0)

            # bidirectional connection between RudpReg and SRPv3
            self.srp = rogue.protocols.srp.SrpV3()
            self.srp == self.RudpReg

        else:

            # Start up flags are FALSE for simulation mode
            self._pollEn   = False
            self._initRead = False

            # Map the simulation memory and stream interfaces
            self.srp    = rogue.interfaces.memory.TcpClient('localhost',10000)
            self.stream = rogue.interfaces.stream.TcpClient('localhost',10002)

        #################################################################

        # Add Devices
        self.add(devBoard.Core(
            offset   = 0x0000_0000,
            memBase  = self.srp,
            sim      = self.sim,
            expand   = True,
        ))

        self.add(devBoard.App(
            offset   = 0x8000_0000,
            memBase  = self.srp,
            sim      = self.sim,
            expand   = True,
        ))

        #################################################################

