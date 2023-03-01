.. _how_to_run_multiple_zmq_clients:

=========================================================
How to run multiple GUI clients on the same KCU105 server
=========================================================

The SURF's RUDP connection only support 1 "physical" client/server connection.  If you need more than 1 software client to access the hardware server, then you can use ZeroMQ for multiple “virtual” connections to the hardware.
This means that you can run multiple ``devGui.py`` scripts
at the same time (refer to :ref:`how_to_software_gui`) because the PyDM GUI does NOT access the hardware directly, but uses a ZeroMQ to manage asynchronous I/O from
multiple clients and manage the hardware access.

How to start the ZMQ server then launch two different ZMQ clients
========================================================================================================

* For the first terminal:

#. Setup rogue software (refer to :ref:`setup_rogue_setup`)

#. Start the ZMQ server (basically devGui script but with ``--guiType None`` argument)

   .. code-block:: bash

      $ cd Simple-10GbE-RUDP-KCU105-Example/software
      $ python scripts/devGui.py --guiType None &


#. Start the 1st ZMQ client

   .. code-block:: bash

      $ python scripts/zmqClientGui.py

* For the second terminal:

#. Start the 2nd ZMQ client

   .. code-block:: bash

      $ cd Simple-10GbE-RUDP-KCU105-Example/software
      $ python scripts/zmqClientGui.py

   .. image:: ../../images/devGui.png
     :width: 800
     :alt: Alternative text

How to get access with another client if ZMQ server is already running
===================================================================

#. Setup rogue software (refer to :ref:`setup_rogue_setup`)

#. Run the ZmqClientGui python script to get access to the devGui's script ZMQ server

   .. code-block:: bash

      $ cd Simple-10GbE-RUDP-KCU105-Example/software
      $ python scripts/zmqClientGui.py

   .. image:: ../../images/zmqClientGui.png
     :width: 800
     :alt: Alternative text
