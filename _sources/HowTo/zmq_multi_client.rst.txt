.. _how_to_run_multiple_zmq_clients:

=========================================================
How to run multiple GUI clients on the same KCU105 server
=========================================================

The SURF's RUDP connection only support 1 "physical" client/server connection.  If you need more than 1 software client to access the hardware server, then you can use ZeroMQ for multiple “virtual” connections to the hardware.
This means that you can run multiple ``devGui.py`` scripts
at the same time (refer to :ref:`how_to_software_gui`) because the PyDM GUI does NOT access the hardware directly, but uses a ZeroMQ to manage asynchronous I/O from
multiple clients and manage the hardware access.


How to get access with another client if PyDM GUI is already opened
===================================================================

#. Setup rogue software (refer to :ref:`setup_rogue_setup`)

#. Run the ZmqClientGui python script to get access to the devGui's script ZMQ server

   .. code-block:: bash

      $ cd Simple-10GbE-RUDP-KCU105-Example/software
      $ python scripts/zmqClientGui.py

   .. image:: ../../images/zmqClientGui.png
     :width: 800
     :alt: Alternative text

How to create a ZMQ server without PyDM GUI in one terminal and ZMQ client with PyDM in another terminal
========================================================================================================

* For the first terminal:

#. Setup rogue software (refer to :ref:`setup_rogue_setup`)

#. Run the Development GUI python script ``--guiType None`` argument

   .. code-block:: bash

      $ cd Simple-10GbE-RUDP-KCU105-Example/software
      $ python scripts/devGui.py --guiType None

* For the second terminal:

#. Run the ZmqClientGui python script to get access to the ZMQ server without a GUI running

   .. code-block:: bash

      $ cd Simple-10GbE-RUDP-KCU105-Example/software
      $ python scripts/zmqClientGui.py

   .. image:: ../../images/devGui.png
     :width: 800
     :alt: Alternative text
