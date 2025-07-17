##############################################################################
## This file is part of 'Simple-10GbE-RUDP-KCU105-Example'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'Simple-10GbE-RUDP-KCU105-Example', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################

##############################################################################
# I/O Constraints
##############################################################################

set_property -dict { PACKAGE_PIN P24 IOSTANDARD DIFF_HSTL_I_18 } [get_ports { phyRxP }]
set_property -dict { PACKAGE_PIN P25 IOSTANDARD DIFF_HSTL_I_18 } [get_ports { phyRxN }]
set_property -dict { PACKAGE_PIN N24 IOSTANDARD DIFF_HSTL_I_18 } [get_ports { phyTxP }]
set_property -dict { PACKAGE_PIN M24 IOSTANDARD DIFF_HSTL_I_18 } [get_ports { phyTxN }]

set_property -dict { PACKAGE_PIN P26 IOSTANDARD LVDS_25 } [get_ports { phyClkP }]
set_property -dict { PACKAGE_PIN N26 IOSTANDARD LVDS_25 } [get_ports { phyClkN }]

set_property -dict { PACKAGE_PIN K25 IOSTANDARD LVCMOS18 } [get_ports { phyIrqN }]
set_property -dict { PACKAGE_PIN L25 IOSTANDARD LVCMOS18 } [get_ports { phyMdc }]
set_property -dict { PACKAGE_PIN H26 IOSTANDARD LVCMOS18 } [get_ports { phyMdio }]
set_property -dict { PACKAGE_PIN J23 IOSTANDARD LVCMOS18 } [get_ports { phyRstN }]

set_property -dict { PACKAGE_PIN AK17 IOSTANDARD DIFF_SSTL12_DCI ODT RTT_48 } [get_ports { sysClk300P }]
set_property -dict { PACKAGE_PIN AK16 IOSTANDARD DIFF_SSTL12_DCI ODT RTT_48 } [get_ports { sysClk300N }]

# PGP differential clk
set_property PACKAGE_PIN T6 [get_ports { pgpClkP }]
set_property PACKAGE_PIN T5 [get_ports { pgpClkN }]
create_clock -name pgpClk -period 6.400 [get_ports { pgpClkP }]

# Use C2M pins here
set_property PACKAGE_PIN F6 [get_ports { pgpTxP[0] }]
set_property PACKAGE_PIN F5 [get_ports { pgpTxN[0] }]
set_property PACKAGE_PIN D6 [get_ports { pgpTxP[1] }]
set_property PACKAGE_PIN D5 [get_ports { pgpTxN[1] }]
set_property PACKAGE_PIN C4 [get_ports { pgpTxP[2] }]
set_property PACKAGE_PIN C3 [get_ports { pgpTxN[2] }]
set_property PACKAGE_PIN B6 [get_ports { pgpTxP[3] }]
set_property PACKAGE_PIN B5 [get_ports { pgpTxN[3] }]

# Use M2C pins here
set_property PACKAGE_PIN E4 [get_ports { pgpRxP[0] }]
set_property PACKAGE_PIN E3 [get_ports { pgpRxN[0] }]
set_property PACKAGE_PIN D2 [get_ports { pgpRxP[1] }]
set_property PACKAGE_PIN D1 [get_ports { pgpRxN[1] }]
set_property PACKAGE_PIN B2 [get_ports { pgpRxP[2] }]
set_property PACKAGE_PIN B1 [get_ports { pgpRxN[2] }]
set_property PACKAGE_PIN A4 [get_ports { pgpRxP[3] }]
set_property PACKAGE_PIN A3 [get_ports { pgpRxN[3] }]

set_property PACKAGE_PIN U4 [get_ports ethTxP]
set_property PACKAGE_PIN U3 [get_ports ethTxN]
set_property PACKAGE_PIN T2 [get_ports ethRxP]
set_property PACKAGE_PIN T1 [get_ports ethRxN]

set_property PACKAGE_PIN P6 [get_ports ethClkP]
set_property PACKAGE_PIN P5 [get_ports ethClkN]

set_property -dict { PACKAGE_PIN V12 IOSTANDARD ANALOG } [get_ports { vPIn }]
set_property -dict { PACKAGE_PIN W11 IOSTANDARD ANALOG } [get_ports { vNIn }]

set_property -dict { PACKAGE_PIN AN8 IOSTANDARD LVCMOS18 } [get_ports { extRst }]

set_property -dict { PACKAGE_PIN AL8  IOSTANDARD LVCMOS18 } [get_ports { sfpTxDisL }]
set_property -dict { PACKAGE_PIN AP10 IOSTANDARD LVCMOS18 } [get_ports { i2cRstL }]
set_property -dict { PACKAGE_PIN J24  IOSTANDARD LVCMOS18 } [get_ports { i2cScl }]
set_property -dict { PACKAGE_PIN J25  IOSTANDARD LVCMOS18 } [get_ports { i2cSda }]

set_property -dict { PACKAGE_PIN AP8 IOSTANDARD LVCMOS18 } [get_ports { led[0] }]
set_property -dict { PACKAGE_PIN H23 IOSTANDARD LVCMOS18 } [get_ports { led[1] }]
set_property -dict { PACKAGE_PIN P20 IOSTANDARD LVCMOS18 } [get_ports { led[2] }]
set_property -dict { PACKAGE_PIN P21 IOSTANDARD LVCMOS18 } [get_ports { led[3] }]
set_property -dict { PACKAGE_PIN N22 IOSTANDARD LVCMOS18 } [get_ports { led[4] }]
set_property -dict { PACKAGE_PIN M22 IOSTANDARD LVCMOS18 } [get_ports { led[5] }]
set_property -dict { PACKAGE_PIN R23 IOSTANDARD LVCMOS18 } [get_ports { led[6] }]
set_property -dict { PACKAGE_PIN P23 IOSTANDARD LVCMOS18 } [get_ports { led[7] }]

set_property -dict { PACKAGE_PIN G26 IOSTANDARD LVCMOS18 } [get_ports { flashCsL }]  ; # QSPI1_CS_B
set_property -dict { PACKAGE_PIN M20 IOSTANDARD LVCMOS18 } [get_ports { flashMosi }] ; # QSPI1_IO[0]
set_property -dict { PACKAGE_PIN L20 IOSTANDARD LVCMOS18 } [get_ports { flashMiso }] ; # QSPI1_IO[1]
set_property -dict { PACKAGE_PIN R21 IOSTANDARD LVCMOS18 } [get_ports { flashWp }]   ; # QSPI1_IO[2]
set_property -dict { PACKAGE_PIN R22 IOSTANDARD LVCMOS18 } [get_ports { flashHoldL }]; # QSPI1_IO[3]

set_property -dict { PACKAGE_PIN K20 IOSTANDARD LVCMOS18 } [get_ports { emcClk }]

##############################################################################
# Timing Constraints
##############################################################################

create_clock -name ethClkP    -period 6.400 [get_ports {ethClkP}]
create_clock -name phyClkP    -period 1.600 [get_ports {phyClkP}]
create_clock -name sysClk300P -period 3.333 [get_ports {sysClk300P}]

# Constraint for marking these clock domains as asynchronous (fix "unsafe" clock interactions)
 set_clock_groups -asynchronous \
        -group [get_clocks -include_generated_clocks *pgpClk*] \
        -group [get_clocks -include_generated_clocks *phyRxClk*] \
        -group [get_clocks -include_generated_clocks *sysClk300P*] \
        -group [get_clocks -include_generated_clocks *ethClkP*] \
        -group [get_clocks -include_generated_clocks *phyClkP*]

##############################################################################
# BITSTREAM: .bit file Configuration
##############################################################################

set_property CONFIG_VOLTAGE 1.8              [current_design]
set_property CFGBVS GND                      [current_design]
set_property CONFIG_MODE SPIx8               [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWID TH 8 [current_design]

set_property BITSTREAM.CONFIG.CONFIGRATE 12  [current_design]
#set_property BITSTREAM.CONFIG.EXTMASTERCCLK_EN div-1 [current_design]
#set_property BITSTREAM.CONFIG.SPI_FALL_EDGE YES [current_design]
set_property BITSTREAM.CONFIG.UNUSEDPIN Pullup [current_design]
set_property BITSTREAM.CONFIG.SPI_32BIT_ADDR Yes [current_design]
set_property BITSTREAM.STARTUP.LCK_CYCLE NoWait [current_design]
set_property BITSTREAM.STARTUP.MATCH_CYCLE NoWait [current_design]
