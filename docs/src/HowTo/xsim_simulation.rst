.. _how_to_xsim_simulation:

====================================================================
How to run the Software Development GUI with XSIM firmware simulator
====================================================================

* Start up two terminals ...

In the first terminal
=====================

#. Setup Vivado (refer to :ref:`setup_vivado_setup`)

#. Go to the target directory and execute the `gui` build, which will launch the Vivado GUI

   .. code-block:: bash

      $ cd Simple-10GbE-RUDP-KCU105-Example/firmware/targets/Simple10GbeRudpKcu105Example
      $ make gui

#. When the Vivado GUI pops up, start the simulation run with "Run Simulation"

   .. image:: ../../images/xsimGui.png
     :width: 800
     :alt: Alternative text

In the Second terminal
======================

#. Setup rogue software (refer to :ref:`setup_rogue_setup`)

#. run the Development GUI python script with **--ip sim** argument

   .. code-block:: bash

      $ cd Simple-10GbE-RUDP-KCU105-Example/software
      $ python scripts/devGui.py --ip sim


   .. image:: ../../images/xsimCosimGui.png
     :width: 800
     :alt: Alternative text
