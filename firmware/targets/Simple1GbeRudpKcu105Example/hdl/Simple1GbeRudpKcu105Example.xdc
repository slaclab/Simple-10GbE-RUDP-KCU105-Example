##############################################################################
## This file is part of 'Simple-10GbE-RUDP-KCU105-Example'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'Simple-10GbE-RUDP-KCU105-Example', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################

set_clock_groups -asynchronous -group [get_clocks ethClkP] -group [get_clocks -of_objects [get_pins U_Core/GEN_ETH.U_Rudp/GEN_1G.U_1GigE/GEN_INT_PLL.U_MMCM/MmcmGen.U_Mmcm/CLKOUT0]]
