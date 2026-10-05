.. _introduction:

============
Introduction
============

The firmware structure for the present example is divided into two main blocks, **Application** and **Core**.

   .. image:: ../images/fw_top.png
     :width: 800
     :alt: Alternative text

The interfaces between the **Core** and the **Application** are **AXI-Lite** and **AXI stream** buses.

The **AXI-Lite** bus is used for register access.

(refer to https://developer.arm.com/documentation/ihi0022/e/)

The **AXI stream** bus is used to transfer ASYNC messages to/from the RUDP module.

(refer to https://developer.arm.com/documentation/ihi0051/a/Introduction/About-the-AXI4-Stream-protocol)

The application block includes an **AppTx** module.
This module is an example of how to produce data on the **AXI stream** bus.
This **AXI stream** bus is connected to the **Core** and routed to the **RUDP** module.
The **RUDP** module contains all the Ethernet layers (PHY/MAC/IPv4/UDP/ReliableLayer).
For the Reliable Layer, we are using the Reliable SLAC Streaming Interface (RSSI)
(refer to https://confluence.slac.stanford.edu/x/1IyfD).
The UdpEngineWrapper module contains the IPv4 and UDP layers.
The TenGigEth module contains the PHY and MAC layers.
A block diagram of this stream path from the Application's **AppTx** module to the PHY layer is shown below:

   .. image:: ../images/fileio_DataStreamFlow.png
     :width: 800
     :alt: Alternative text

The **Application** module is designed to be a "template" for developers.
They can copy the firmware modules and structure, then customize them to their specific applications.
Developers can treat the **Core** module as a Board Support Package (BSP).
