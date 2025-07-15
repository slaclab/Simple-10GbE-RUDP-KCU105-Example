.. _setup_rogue_setup:

====================
Rogue Software Setup
====================

If you are on the SLAC SDF network
==================================

Here's how to setup the SLAC SDF conda build of rogue:

.. code-block:: bash

   $ cd Simple-10GbE-RUDP-KCU105-Example/software
   $ source setup_env_slac.sh

If you are NOT on the SLAC SDF network
======================================

Here is "How to install the Rogue With Miniforge":

   https://slaclab.github.io/rogue/installing/miniforge.html

After doing the local Miniforge install, you will need to setup the conda enviroment

.. code-block:: bash

   # Setup conda environment
   $ source /path/to/my/miniforge3/etc/profile.d/conda.sh

   # Activate Rogue conda Environment
   $ conda activate rogue_v6.4.4
