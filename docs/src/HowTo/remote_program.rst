.. _how_to_remote_program:

===================================================
How to reprogram your KCU105 board's QSPI Boot Prom
===================================================

#. The KCU105 **MUST** have a version of the Simple10GbeRudpKcu105Example firmware loaded. If first time to program KCU105 with Simple10GbeRudpKcu105Example, then use the JTAG and load the .bit file into the FPGA. Follow these steps only if this is the first time that you are loading the firmware:

   #. Disconnect the USB from the JTAG.
 
   #. If you are at SLAC, go to the cable driver directory:

        .. code-block::

                $ cd /afs/slac.stanford.edu/g/reseng/vol34/xilinx/2021.1/Vivado/2021.1/data/xicom/cable_drivers/lin64/install_script/install_drivers/
 
   #. Execute the “install drivers” scripts as “sudo”:

        .. code-block::
        
                $ sudo ./install_drivers

   #. Follow the steps in the tutorial below for lab#5 and step#1~9 on page 47 ~ 53:
 
        https://www.xilinx.com/support/documentation/sw_manuals/xilinx2021_1/ug936-vivado-tutorial-programming-debugging.pdf

#. Make sure SW15 is setup for QSPI booting (refer to :ref:`setup_hardware_setup`)

#. Build the firmware (refer to :ref:`how_to_build_firmware`) so that there are .MCS files in the "Simple-10GbE-RUDP-KCU105-Example/firmware/targets/Simple10GbeRudpKcu105Example/images" directory.

#. Setup rogue software (refer to :ref:`setup_rogue_setup`)

#. Run the reprogramming script

   .. code-block::

        $ python software/scripts/updateBootProm.py --path <PATH_TO_IMAGE_DIR>*)

   Example of the script output:

   .. code-block::

      $ python software/scripts/updateBootProm.py --path firmware/targets/Simple10GbeRudpKcu105Example/images/
      Rogue/pyrogue version v5.8.0. https://github.com/slaclab/rogue
      Start: Started zmqServer on ports 9107-9109
      Root.Core.AxiVersion count reset called
      ###################################################
      #                 Old Firmware                    #
      ###################################################
      Path         = Root.Core.AxiVersion
      FwVersion    = 0x1000000
      UpTime       = 16:32:03
      GitHash      = dirty (uncommitted code)
      XilinxDnaId  = 0x4002000100f1cd4544618485
      FwTarget     = Simple10GbeRudpKcu105Example
      BuildEnv     = Vivado v2021.1
      BuildServer  = rdsrv307 (Ubuntu 20.04.2 LTS)
      BuildDate    = Thu 15 Jul 2021 01:44:36 PM PDT
      Builder      = ruckman
      0 : firmware/targets/Simple10GbeRudpKcu105Example/images/Simple10GbeRudpKcu105Example-0x01000000-20210715134436-ruckman-dirty
      1 : firmware/targets/Simple10GbeRudpKcu105Example/images/Simple10GbeRudpKcu105Example-0x01000000-20210716121151-ruckman-50550dd
      Enter image to program into the PCIe card's PROM: 1
      Root.Core.AxiMicronN25Q[0].LoadMcsFile: firmware/targets/Simple10GbeRudpKcu105Example/images/Simple10GbeRudpKcu105Example-0x01000000-20210716121151-ruckman-50550dd_primary.mcs.gz
      PROM Manufacturer ID Code  = 0x20
      PROM Manufacturer Type     = 0xbb
      PROM Manufacturer Capacity = 0x19
      PROM Status Register       = 0x2
      PROM Volatile Config Reg   = 0xfb
      Reading .MCS:    [####################################]  100%
      Erasing PROM:    [####################################]  100%
      Writing PROM:    [####################################]  100%
      Verifying PROM:  [####################################]  100%
      LoadMcsFile() took 0:00:50 to program the PROM


                  ***************************************************
                  ***************************************************
                  The MCS data has been written into the PROM.
                  To reprogram the FPGA with the new PROM data,
                  a IPROG CMD or power cycle is be required.
                  ***************************************************
                  ***************************************************


      Root.Core.AxiMicronN25Q[1].LoadMcsFile: firmware/targets/Simple10GbeRudpKcu105Example/images/Simple10GbeRudpKcu105Example-0x01000000-20210716121151-ruckman-50550dd_secondary.mcs.gz
      PROM Manufacturer ID Code  = 0x20
      PROM Manufacturer Type     = 0xbb
      PROM Manufacturer Capacity = 0x19
      PROM Status Register       = 0x2
      PROM Volatile Config Reg   = 0xfb
      Reading .MCS:    [####################################]  100%
      Erasing PROM:    [####################################]  100%
      Writing PROM:    [####################################]  100%
      Verifying PROM:  [####################################]  100%
      LoadMcsFile() took 0:00:49 to program the PROM


                  ***************************************************
                  ***************************************************
                  The MCS data has been written into the PROM.
                  To reprogram the FPGA with the new PROM data,
                  a IPROG CMD or power cycle is be required.
                  ***************************************************
                  ***************************************************



      Reloading FPGA firmware from PROM ....

      Reloading FPGA done
      ###################################################
      #                 New Firmware                    #
      ###################################################
      Path         = Root.Core.AxiVersion
      FwVersion    = 0x1000000
      UpTime       = 0:00:04
      GitHash      = 0x50550dd2881fed3f48af0ca0db8a78da9f3e2363
      XilinxDnaId  = 0x4002000100f1cd4544618485
      FwTarget     = Simple10GbeRudpKcu105Example
      BuildEnv     = Vivado v2021.1
      BuildServer  = rdsrv307 (Ubuntu 20.04.2 LTS)
      BuildDate    = Fri 16 Jul 2021 12:11:51 PM PDT
      Builder      = ruckman
