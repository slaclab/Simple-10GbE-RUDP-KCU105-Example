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

The **AXI stream** bus to transfer ASYNC messages to/from the RUDP module

(refer to https://developer.arm.com/documentation/ihi0051/a/Introduction/About-the-AXI4-Stream-protocol)

Inside the application block includes a **AppTx** module.
This module is an example of how to produce data on the **AXI stream** bus.
This **AXI steam** bus is connected to the **Core** and routed to the **RUDP** module.
The **RUDP** module contains all the Ethernet layers (PHY/MAC/IPv4/UDP/ReliableLayer).
For the Reliable Layer, we are using are using Reliable SLAC Streaming Protocol (RSSI)
(refer to https://confluence.slac.stanford.edu/x/1IyfD).
UdpEngineWrapper module contains the IPv4 and UDP layers.
TenGigEth module contains the PHY and MAC layers.
A block diagram on this stream path from the Application's **AppTx** module to the PHY layer is shown below:

   .. image:: ../images/fileio_DataStreamFlow.png
     :width: 800
     :alt: Alternative text

The **Application** module is designed to be a "template" for developers.
They can copy the firmware modules and structure then customize it to their specific applications.
Developers can treat the **core** module has a Board Support Package (BSP).
