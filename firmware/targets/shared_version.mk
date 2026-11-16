# Define Firmware Version: v4.0.0.0
export PRJ_VERSION = 0x04000000

# Define target output
target: prom

# Define target part
export PRJ_PART = XCKU040-FFVA1156-2-E

# Using XVC Debug bridge
export USE_XVC_DEBUG = 1

# Define release
ifndef RELEASE
export RELEASE = simple_10gbe_rudp_kcu105_example
endif
