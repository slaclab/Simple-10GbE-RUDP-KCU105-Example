.. _how_to_use_fileio:

==============================================
How to Use the Rogue FileWriter and FileReader
==============================================

Rogue includes a general-purpose file writer and file reader
to quickly write data to disk and analyze it offline.


#. Start up the PyDM GUI (refer to :ref:`how_to_software_gui`)

#. Go to the ``System`` tab (A), click on ``Auto Name`` (B), then click on ``Open`` (C)

   .. image:: ../../images/fileio_0.png
     :width: 800
     :alt: Alternative text

#. Go to the ``Debug Tree`` tab, navigate to ``Root.App.SsiPrbsTx`` and set ``TxEn`` to ``True``

   .. image:: ../../images/fileio_1.png
     :width: 800
     :alt: Alternative text

#. Go back to ``Root.App.SsiPrbsTx`` and set ``TxEn`` to ``False`` once the frame count in the ``System`` tab has reached at least 256

#. Go to the ``System`` tab, check the frame count (A), and click on ``Close`` (B)

   .. image:: ../../images/fileio_3.png
     :width: 800
     :alt: Alternative text

#. Close the PyDM GUI

#. Run the fileReader python script, which replays the file through a software PRBS receiver

   .. code-block:: bash

      $ python scripts/fileReader.py --dataFile data_20220614_092954.dat
      Rogue/pyrogue version v6.17.0. https://github.com/slaclab/rogue
      Start: Started zmqServer on ports 9099-9101
          To start a gui: python -m pyrogue gui --server='localhost:9099'
          To use a virtual client: client = pyrogue.interfaces.VirtualClient(addr='localhost', port=9099)
      rxCount  = 256
      rxBytes  = 8388608
      rxErrors = 0

#. ``rxCount`` is the number of PRBS frames found in the file and ``rxErrors`` should be zero
