# Load RUCKUS library
source $::env(RUCKUS_PROC_TCL)

# Check for version 2023.1 of Vivado (or later)
if { [VersionCheck 2023.1] < 0 } {exit -1}

# Load Source Code
loadSource -dir  "$::DIR_PATH/rtl"
loadIpCore -path "$::DIR_PATH/ip/SystemManagementCore.xci"
loadConstraints -dir "$::DIR_PATH/xdc"
