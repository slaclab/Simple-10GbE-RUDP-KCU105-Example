.. _how_to_prbs_streaming:

===========================================
How to Run the PRBS Stream Test (FW <-> SW)
===========================================

The RUDP[1] data stream has a PRBS transmitter and a PRBS receiver on both ends:

* ``Root.App.SsiPrbsTx`` (FW) streams PRBS frames to ``Root.SwPrbsRx`` (SW)
* ``Root.SwPrbsTx`` (SW) streams PRBS frames to ``Root.App.SsiPrbsRx`` (FW)

This makes it possible to load the RSSI link in one direction at a time, or in both directions at once.

#. Start up the PyDM GUI (refer to :ref:`how_to_software_gui`) and go to the ``Debug Tree`` tab

#. Clear all the counters with ``Root.CountReset``

#. FW to SW direction: navigate to ``Root.App.SsiPrbsTx``, optionally adjust ``PacketLength`` (units of 64-bit words), and set ``TxEn`` to ``True``

   * ``Root.SwPrbsRx.rxCount`` increments and ``Root.SwPrbsRx.rxErrors`` should stay at zero
   * ``Root.Core.AxisMon.Ch[0]`` shows the FW TX bandwidth

#. SW to FW direction: navigate to ``Root.SwPrbsTx``, optionally adjust ``txSize`` (bytes) and ``txPeriod`` (microseconds), and set ``txEnable`` to ``True``

   * ``Root.App.SsiPrbsRx.FrameCnt`` increments and the ``SsiPrbsRx`` error counters should stay at zero
   * ``Root.Core.AxisMon.Ch[1]`` shows the FW RX bandwidth

#. Both directions at once: enable both ``TxEn`` and ``txEnable`` and monitor the ``Root.Core.FwRudpServer[1]`` link status and counters

#. Set ``TxEn`` and ``txEnable`` back to ``False`` to stop the streaming
