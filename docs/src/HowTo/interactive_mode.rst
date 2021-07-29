.. _how_to_run_interactive_mode

=========================================================
How to run the Software in Interactive Mode
=========================================================

#. Setup rogue software (refer to :ref:`setup_rogue_setup`)

#. Run the interactive python script with the **-i** argument

   .. code-block:: bash

      $ cd Simple-10GbE-RUDP-KCU105-Example/software
      $ ipython -i -- scripts/interactive.py
      Python 3.7.10 | packaged by conda-forge | (default, Feb 19 2021, 16:07:37)
      Type 'copyright', 'credits' or 'license' for more information
      IPython 7.23.1 -- An enhanced Interactive Python. Type '?' for help.
      Rogue/pyrogue version v5.8.0. https://github.com/slaclab/rogue
      Start: Started zmqServer on ports 9099-9101
      Root.Core.AxiVersion count reset called
      ###################################################
      #             Firmware Version                    #
      ###################################################
      Path         = Root.Core.AxiVersion
      FwVersion    = 0x1010000
      UpTime       = 8 days, 22:45:50
      GitHash      = 0xa75a5f55b0ea87cb5b66f1ea1bff12272ae1bc73
      XilinxDnaId  = 0x4002000100fa6901008125c1
      FwTarget     = Simple10GbeRudpKcu105Example
      BuildEnv     = Vivado v2021.1
      BuildServer  = rdsrv303 (Ubuntu 20.04.2 LTS)
      BuildDate    = Mon 19 Jul 2021 08:42:18 AM PDT
      Builder      = ruckman
      ###################################################
      AxiVersion.ScratchPad.get()     = 3735928559
      AxiVersion.ScratchPad.getDisp() = 0xdeadbeef

      In [1]:

#. You now have an interactive command terminal to the rogue software.

#. As an example, let's change the ScratchPad from 0xdeadbeef to 0x12345678

   .. code-block:: bash

      In [1]: root.Core.AxiVersion.ScratchPad.getDisp()
      Out[1]: '0xdeadbeef'

      In [2]: root.Core.AxiVersion.ScratchPad.setDisp(0x12345678)

      In [3]: root.Core.AxiVersion.ScratchPad.getDisp()
      Out[3]: '0x12345678'
