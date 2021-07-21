.. _how_to_setup_fw_for_fileio:

============================================
How the file IO firmware example is defined
============================================

#. The firmware structure for the present example is divided into two main blocks, Application and Core.

#. The application block includes the AppTx module that, for this example, simulates a data generator producing an AXI stream. The stream
   is connected to the core.

#. In the core, the Axi stream is routed to the Rudp module that is responsible framing the incoming data stream,
   effectively going from the ISO_OSI model application layer to the transport layer.

#. The RSSI output data then is encapsulated into the UDP protocol. Finally the UDP stream is sent to the
   10Gbps UltraScale transceiver to complete the firmware flow.


   .. image:: ../../images/fileio_dataStreamFlow.png
     :width: 800
     :alt: Alternative text


#. The developer is expected to heavely change the applicaion submodules to fit the real system requirement, but on the core side
   a high level of reuse is mostlikly the case.
