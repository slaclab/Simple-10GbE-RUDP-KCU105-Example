# Load RUCKUS library
source $::env(RUCKUS_PROC_TCL)

# Load Source Code
loadSource -dir  "$::DIR_PATH/rtl"
loadIpCore -path "$::DIR_PATH/ip/SystemManagementCore.xci"
loadConstraints -dir "$::DIR_PATH/xdc"
