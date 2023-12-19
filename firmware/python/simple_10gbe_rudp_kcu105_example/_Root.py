#-----------------------------------------------------------------------------
# This file is part of the 'Simple-10GbE-RUDP-KCU105-Example'. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the 'Simple-10GbE-RUDP-KCU105-Example', including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------

import pyrogue  as pr
import pyrogue.protocols
import pyrogue.utilities.fileio
import pyrogue.interfaces.simulation

import rogue
import rogue.hardware.axi
import rogue.interfaces.stream
import rogue.utilities.fileio

import simple_10gbe_rudp_kcu105_example as devBoard

rogue.Version.minVersion('6.0.0')

class Root(pr.Root):
    def __init__(   self,
            ip       = '192.168.3.10',
            promProg = False, # Flag to disable all devices not related to PROM programming
            enSwRx   = True,  # Flag to enable the software stream receiver
            zmqSrvEn = True,  # Flag to include the ZMQ server
            **kwargs):
        super().__init__(**kwargs)

        self.enSwRx = not promProg and enSwRx
        self.sim    = (ip == 'sim')

        # Check if including ZMQ server (required for PyDM GUI)
        if zmqSrvEn:
            self.zmqServer = pr.interfaces.ZmqServer(root=self, addr='*', port=0)
            self.addInterface(self.zmqServer)

        #################################################################

        # Check if running in HW emulation mode
        if (ip == 'emu'):

            # Emulate the memory and stream interfaces
            self.srp =  pr.interfaces.simulation.MemEmulate()
            self.stream = rogue.interfaces.stream.Master()

        # Check if VCS FW/SW co-simulation
        elif (ip == 'sim'):

            # Firmware simulation slow and timeout base on real time (not simulation time)
            self._timeout = 100000000

            # Override start up flags are FALSE for simulation mode
            self._pollEn   = False
            self._initRead = False

            # Map the simulation memory and stream interfaces
            self.srp    = rogue.interfaces.memory.TcpClient('localhost',10000)
            self.stream = rogue.interfaces.stream.TcpClient('localhost',10002)

        # Else communicating to the actual hardware
        else:

            # Add Software clients
            self.udpClts = [None for i in range(2)]

            for i in range(2):
                self.udpClts[i] = rogue.protocols.udp.Client(  ip, 8192+i, 1500 )

            # Create SRPv3
            self.srp = rogue.protocols.srp.SrpV3()

            # Connect SRPv3 to udpClts[0]
            self.srp == self.udpClts[0]

            # Map the streaming interface
            self.stream = self.udpClts[1]

            # Create XVC server and UDP client
            self.udpClient = rogue.protocols.udp.Client( ip, 2542, False ) # Client(host, port, jumbo)
            self.xvc = rogue.protocols.xilinx.Xvc ( 2542 ) # Server(port)
            self.addProtocol( self.xvc )

            # Connect the UDP Client to the XVC
            self.udpClient == self.xvc

        #################################################################

        # Check for streaming enabled
        if self.enSwRx:

            # File writer
            self.dataWriter = pr.utilities.fileio.StreamWriter()
            self.add(self.dataWriter)

            # Create application stream receiver
            self.swRx = devBoard.SwRx(expand=True)
            self.add(self.swRx)

            # Connect stream to swRx
            self.stream >> self.swRx

            # Also connect stream to data writer
            self.stream >> self.dataWriter.getChannel(0)

        #################################################################

        # Add Devices
        self.add(devBoard.Core(
            offset   = 0x0000_0000,
            memBase  = self.srp,
            sim      = self.sim,
            promProg = promProg,
            expand   = True,
        ))

        if not promProg:
            self.add(devBoard.App(
                offset   = 0x8000_0000,
                memBase  = self.srp,
                sim      = self.sim,
                expand   = True,
            ))

        #################################################################

    def start(self, **kwargs):
        super().start(**kwargs)
        # Check if not simulation
        if not self.sim:
            appTx = self.find(typ=devBoard.AppTx)
            # Turn off the Continuous Mode
            for devPtr in appTx:
                devPtr.ContinuousMode.set(False)
            self.CountReset()
