# Load RUCKUS environment and library
source $::env(RUCKUS_PROC_TCL)

# Check for version 2023.1 of Vivado (or later)
if { [VersionCheck 2023.1] < 0 } {exit -1}

# Load shared and sub-module ruckus.tcl files
loadRuckusTcl $::env(TOP_DIR)/submodules/surf
loadRuckusTcl $::env(TOP_DIR)/shared

# Load local source Code and constraints
loadSource      -dir "$::DIR_PATH/hdl"
loadConstraints -dir "$::DIR_PATH/hdl"

# Modified the .XDC property
set_property PROCESSING_ORDER {EARLY}                    [get_files {GigEthLvdsUltraScaleCore.xdc}]
set_property SCOPED_TO_REF    {GigEthLvdsUltraScaleCore} [get_files {GigEthLvdsUltraScaleCore.xdc}]
set_property SCOPED_TO_CELLS  {U0}                       [get_files {GigEthLvdsUltraScaleCore.xdc}]

# Load local SIM source Code
loadSource -sim_only -dir  "$::DIR_PATH/tb"
set_property top {SimpleRj45RudpKcu105ExampleTb} [get_filesets sim_1]
