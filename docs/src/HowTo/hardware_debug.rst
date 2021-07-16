.. _how_to_hardware_debug:

====================================================
How to implement ILA/Chipscope in Vivado with ruckus
====================================================

* Add a "post_synthesis.tcl" to your target's vivado directory.  Here's an example

   *firmware/targets/Simple10GbeRudpKcu105Example/vivado/post_synthesis.tcl*


* Here the basic format of the TCL script

   * Add the ruckus helper functions

   .. code-block::
   
      ##############################
      # Get variables and procedures
      ##############################
      source -quiet $::env(RUCKUS_DIR)/vivado_env_var.tcl
      source -quiet $::env(RUCKUS_DIR)/vivado_proc.tcl

   * Use a "return" if you want to bypass this TCL script

   .. code-block::

      ######################################################
      # Bypass the debug chipscope generation via return cmd
      # ELSE ... comment out the return to include chipscope
      ######################################################
      #return

   * This script gets called after "synth_1" and will open up the synth_1 design

   .. code-block::

      ############################
      ## Open the synthesis design
      ############################
      open_run synth_1

   * Define "ilaName" variable and create the ILA core

   .. code-block::

      ###############################
      ## Set the name of the ILA core
      ###############################
      set ilaName u_ila_0

      ##################
      ## Create the core
      ##################
      CreateDebugCore ${ilaName}

   * Define the record depth and other Vivado properties that you want for the ILA core

   .. code-block::


      #######################
      ## Set the record depth
      #######################
      set_property C_DATA_DEPTH 1024 [get_debug_cores ${ilaName}]

   * Define the clock's netname

   .. code-block::

      #################################
      ## Set the clock for the ILA core
      #################################
      SetDebugCoreClk ${ilaName} {<clock_netname>}


   * Define the probes' netname

   .. code-block::
   
      #######################
      ## Set the debug Probes
      #######################

      ConfigProbe ${ilaName} {<probe_netname>}
      ConfigProbe ${ilaName} {<probe_netname>}
      ...
      ...
      ...
      ConfigProbe ${ilaName} {<probe_netname>}

   * Write the debug probes into the synth_1 design before impl_1

   .. code-block::
   
      ##########################
      ## Write the port map file
      ##########################
      WriteDebugProbes ${ilaName}   

   * Ruckus will automatically copy the ILA file (.ltx) to the target's image directory at the end of the build if it exists.