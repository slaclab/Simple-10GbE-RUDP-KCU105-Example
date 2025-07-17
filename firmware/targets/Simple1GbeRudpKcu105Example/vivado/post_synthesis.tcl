##############################################################################
## This file is part of 'Simple-10GbE-RUDP-KCU105-Example'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'Simple-10GbE-RUDP-KCU105-Example', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################

##############################
# Get variables and procedures
##############################
source -quiet $::env(RUCKUS_DIR)/vivado_env_var.tcl
source $::env(RUCKUS_PROC_TCL)

######################################################
# Bypass the debug chipscope generation via return cmd
# ELSE ... comment out the return to include chipscope
######################################################
#return

############################
## Open the synthesis design
############################
open_run synth_1

###############################
## Set the name of the ILA core
###############################
set ilaName u_ila_0

##################
## Create the core
##################
CreateDebugCore ${ilaName}

#######################
## Set the record depth
#######################
set_property C_DATA_DEPTH 1024 [get_debug_cores ${ilaName}]

#################################
## Set the clock for the ILA core
#################################
SetDebugCoreClk ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/axilClk}


##################################
## JTAG commands for IBERT IP core
##################################
set_property BITSTREAM.GENERAL.DEBUGBITSTREAM Yes [current_design]
set_property BITSTREAM.CONFIG.EN_BSCAN Yes [current_design]
catch { set_property C_EN_VIO_REFRESH false [get_debug_cores -of_objects [get_cells *dbg_hub*]] }

#######################
## Set the debug Probes
#######################

ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/ack[resp][*]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/i2cRegMasterOut[regFailCode][*]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/r_reg[state][*]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/sAxilReadSlave[rresp][*]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/xbarReadSlave[rresp][*]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/ack[done]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/i2cRegMasterOut[regAck]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/i2cRegMasterOut[regFail]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/mAxilReadMasters[*][arvalid]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/mAxilReadSlaves[*][arready]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/mAxilReadSlaves[*][rvalid]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/mAxilReadMasters[*][rready]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/sAxilReadMaster[arvalid]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/sAxilReadMaster[rready]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/sAxilReadSlave[arready]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/sAxilReadSlave[rvalid]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/xbarReadMaster[arvalid]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/xbarReadMaster[rready]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/xbarReadSlave[arready]}
ConfigProbe ${ilaName} {U_Core/GEN_REAL.U_XbarI2cMux/xbarReadSlave[rvalid]}

##########################
## Write the port map file
##########################
WriteDebugProbes ${ilaName}
