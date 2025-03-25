.. _setup_hardware_setup:

==============
Hardware Setup
==============

You will need one Xilinx KCU105 development board:

   https://www.xilinx.com/products/boards-and-kits/kcu105.html

You will need a 10GbE SFP+ transceiver for the KCU105 and
fiber optic cable.  Here's an example of a SFP+ transceiver:

   https://www.fs.com/products/74668.html

You will also need a fiber optic cable as well.
Here's an example of a optical cable:

   https://www.fs.com/products/40180.html

.. image:: ../../images/kcu105_hw.png
  :width: 800
  :alt: Alternative text

For booting up the KCU105 via the QSPI PROM, you will need to setup the SW15 switch
with position#1 in the arrow direction:

.. image:: ../../images/SW15.png
  :width: 800
  :alt: Alternative text

You will also need a micro USB cable to load the firmware for the first time, using the JTAG-to-USB connector on the board (`here are the instructions for programming the KCU105 for the 1st time with SLAC firmware <https://docs.google.com/presentation/d/1ANiM92PP5BN3exUhUnahFOepXYiiALVsTczf8t8YVJ0/edit?usp=sharing>`_).
