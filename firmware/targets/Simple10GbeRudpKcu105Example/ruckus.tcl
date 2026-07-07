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

# Load local SIM source Code
loadSource -sim_only -dir  "$::DIR_PATH/tb"
# Select which xsim demo TB is elaborated as sim_1's top -- switch manually per demo run
set_property top {RogueTcpStreamXsimDemoTb} [get_filesets sim_1]
# set_property top {RogueTcpMemoryXsimDemoTb} [get_filesets sim_1]
