.. _how_to_use_fileio:

==========================================
How to the Rogue FileWriter and FileReader
==========================================

Rogue includes a general purpose file write and file reader
to quickly write data to disk and analysis offline.


#. Start up the PyDM gui (refer to :ref:`how_to_software_gui`)

#. Go to the ``System`` tab (A), click on ``Auto Name`` (B), then click on ``Open`` (C)

   .. image:: ../../images/fileio_0.png
     :width: 800
     :alt: Alternative text

# Go to the ``Variable`` tab and nagivate to ``Root.App.AppTx`` and execute 0x100 for ``SendFrame``

   .. image:: ../../images/fileio_1.png
     :width: 800
     :alt: Alternative text

#. Go to the ``System`` tab and click on ``Close``

   .. image:: ../../images/fileio_2.png
     :width: 800
     :alt: Alternative text

#. Close the PyDM GUI

#. Run the fileReader python script

   .. code-block:: bash

      $ python scripts/fileReader.py --dataFile data_20210719_194217.dat
      Rogue/pyrogue version v5.8.0. https://github.com/slaclab/rogue
      Start: Started zmqServer on ports 9099-9101
      eventFrame.header = 0
      eventFrame.header = 1
      eventFrame.header = 2
      ...
      ...
      ...
      eventFrame.header = 253
      eventFrame.header = 254
      eventFrame.header = 255

#. As you can see, the 256 (0x100) headers are printed out (1 header per frame)
