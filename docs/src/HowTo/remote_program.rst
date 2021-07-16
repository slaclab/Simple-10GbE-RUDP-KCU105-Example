.. _how_to_remote_program:

===================================================
How to reprogram your KCU105 board's QSPI Boot Prom
===================================================

1) The KCU105 **MUST** have a version of the Simple10GbeRudpKcu105Example firmware loaded.
If first time to program KCU105 with Simple10GbeRudpKcu105Example, then use the JTAG 
and load the .bit file into the FPGA.

2) Make sure SW15 is setup for QSPI booting (refer to :ref:`requirements_hardware_setup`)

3) Build the firmware (refer to :ref:`how_to_build_firmware`) to that there is .MCS files
in the "targets/Simple10GbeRudpKcu105Example/images" directory.

4) Setup rogue software (refer to :ref:`requirements_rogue_setup`)

5) Run the reprogramming script

.. code-block:: bash

   $ python scripts/updateBootProm.py --path ../firmware/targets/Simple10GbeRudpKcu105Example/images/
