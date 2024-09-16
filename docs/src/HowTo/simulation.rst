.. _how_to_simulation:

===================================================================
How to run the Software Development GUI with VCS firmware simulator
===================================================================

* Start up two terminals ...

In the first terminal
=====================

#. Follow the instructions `here <https://github.com/slaclab/tid-id-xilinx-dockers/blob/main/README.md>`_ to build and use the `vcs` docker container.

#. Once in the container, setup Vivado and VCS (refer to :ref:`setup_vivado_setup`)

#. Go to the target directory and execute the `vcs` build

   .. code-block:: bash

      $ cd Simple-10GbE-RUDP-KCU105-Example/firmware/targets/Simple10GbeRudpKcu105Example
      $ make vcs

#. Go to the VCS build output

   .. code-block:: bash

      $ cd ../../build/Simple10GbeRudpKcu105Example/Simple10GbeRudpKcu105Example_project.sim/sim_1/behav/

#. Source the VCS + VHPI environment setup

   .. code-block:: bash

      $ source setup_env.sh

#. Compile firmware with VCS

   .. code-block:: bash

      $ ./sim_vcs_mx.sh

#. Launch the VCS GUI (either DVE or VERDI)

   .. code-block:: bash

      $ ./simv -verdi &

#. When the VCS GUI pops up, start the simulation run

   .. image:: ../../images/vcsGui.png
     :width: 800
     :alt: Alternative text

In the Second terminal
======================

#. Setup rogue software (refer to :ref:`setup_rogue_setup`)

#. run the Development GUI python script with **--ip sim** argument

   .. code-block:: bash

      $ cd Simple-10GbE-RUDP-KCU105-Example/software
      $ python scripts/devGui.py --ip sim


   .. image:: ../../images/cosimGui.png
     :width: 800
     :alt: Alternative text
