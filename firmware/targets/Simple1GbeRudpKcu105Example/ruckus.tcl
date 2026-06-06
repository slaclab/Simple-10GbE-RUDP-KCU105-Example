# Load RUCKUS environment and library
source $::env(RUCKUS_PROC_TCL)

# Load shared and sub-module ruckus.tcl files
loadRuckusTcl $::env(TOP_DIR)/submodules/surf
loadRuckusTcl $::env(TOP_DIR)/shared

# Load local source Code and constraints
loadSource      -dir "$::DIR_PATH/hdl"
loadConstraints -dir "$::DIR_PATH/hdl"

# Load local SIM source Code
loadSource -sim_only -dir  "$::DIR_PATH/tb"
set_property top {Simple1GbeRudpKcu105ExampleTb} [get_filesets sim_1]
