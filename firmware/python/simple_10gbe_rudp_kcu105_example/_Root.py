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
            ip       = '192.168.2.10',
            promProg = False, # Flag to disable all devices not related to PROM programming
            enSwRx   = True,  # Flag to enable the software stream receiver
            zmqSrvEn = True,  # Flag to include the ZMQ server
            xvcSrvEn = True,  # Flag to include the XVC server
            **kwargs):

        # Pass custom value to parent via super function
        kwargs['timeout'] = 5.0 if (ip != 'sim') else 100.0 # Firmware simulation slow and timeout base on real time (not simulation time)
        super().__init__(**kwargs)

        self.enSwRx = not promProg and enSwRx
        self.promProg = promProg
        self.sim    = (ip == 'sim')

        # Check if including ZMQ server (required for PyDM GUI)
        if zmqSrvEn:
            self.zmqServer = pr.interfaces.ZmqServer(root=self, addr='127.0.0.1', port=0)
            self.addInterface(self.zmqServer)

        #################################################################

        # Check if running in HW emulation mode
        if (ip == 'emu'):

            # Emulate the memory and stream interfaces
            self.srp =  pr.interfaces.simulation.MemEmulate()
            self.stream = rogue.interfaces.stream.Master()

        # Check if VCS FW/SW co-simulation
        elif (ip == 'sim'):

            # Override start up flags are FALSE for simulation mode
            self._pollEn   = False
            self._initRead = False

            # Map the simulation memory and stream interfaces
            self.srp    = rogue.interfaces.memory.TcpClient('localhost',10000)
            self.stream = rogue.interfaces.stream.TcpClient('localhost',10002)

        # Else communicating to the actual hardware
        else:

            # Add RUDP Software clients
            self.rudp = [None for i in range(2)]

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


            # Create SRPv3
            self.srp = rogue.protocols.srp.SrpV3()

            # Connect SRPv3 to RDUP[0]
            self.srp == self.rudp[0].application(0)

            # Map the streaming interface
            self.stream = self.rudp[1].application(0)

            if not self.promProg and xvcSrvEn:
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
