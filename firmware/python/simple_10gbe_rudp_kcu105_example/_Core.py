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

import surf.axi                  as axi
import surf.devices.micron       as micron
import surf.devices.transceivers as xceiver
import surf.ethernet.udp         as udp
import surf.ethernet.ten_gig     as mac
import surf.protocols.rssi       as rssi
import surf.xilinx               as xil

class Core(pr.Device):
    def __init__( self,sim=False,**kwargs):
        super().__init__(**kwargs)

        self.add(axi.AxiVersion(
            offset = 0x0000_0000,
            expand = True,
        ))

        self.add(xil.AxiSysMonUltraScale(
            offset  = 0x0001_0000,
            enabled = not sim,
        ))

        for i in range(2):
            self.add(micron.AxiMicronN25Q(
                name         = f'AxiMicronN25Q[{i}]',
                offset       = 0x0002_0000 + (i * 0x0001_0000),
                hidden       = True,
                enabled      = not sim,
            ))

        self.add(mac.TenGigEthReg(
            offset  = 0x0010_0000,
            enabled = not sim,
        ))

        self.add(udp.UdpEngine(
            offset  = 0x0011_0000,
            numSrv  = 2,
            enabled = not sim,
        ))

        for i in range(2):
            self.add(rssi.RssiCore(
                name    = f'FwRudpServer[{i}]',
                offset  = 0x0012_0000 + (i * 0x0001_0000),
                enabled = not sim,
            ))

        self.add(axi.AxiStreamMonAxiL(
            name        = 'AxisMon',
            offset      = 0x0014_0000,
            numberLanes = 2,
            expand      = True,
            enabled     = not sim,
        ))

        # Don't example the FW RX AXI stream monitor
        self.AxisMon.Ch[0]._expand = True

        # Don't example the FW RX AXI stream monitor
        self.AxisMon.Ch[1]._expand = False

        self.add(xceiver.Sfp(
            offset      = 0x0020_2000,
            enabled     = not sim,
        ))