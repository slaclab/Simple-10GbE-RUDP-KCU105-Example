# Load RUCKUS environment and library
source $::env(RUCKUS_PROC_TCL)

# Load shared and sub-module ruckus.tcl files
loadRuckusTcl $::env(TOP_DIR)/submodules/surf
loadRuckusTcl $::env(TOP_DIR)/shared

# Load local source Code and constraints
loadSource      -dir "$::DIR_PATH/hdl"
loadConstraints -dir "$::DIR_PATH/../SimpleRj45RudpKcu105Example/hdl"

# Modified the .XDC property
set_property PROCESSING_ORDER {EARLY}                    [get_files {GigEthLvdsUltraScaleCore.xdc}]
set_property SCOPED_TO_REF    {GigEthLvdsUltraScaleCore} [get_files {GigEthLvdsUltraScaleCore.xdc}]
set_property SCOPED_TO_CELLS  {U0}                       [get_files {GigEthLvdsUltraScaleCore.xdc}]
