.. _setup_network_setup:

=============
Network Setup
=============

You will need to configure your 10G NIC card accordingly. Two things are
needed:

1. Configure the card to operate on the 192.168.2.xxx subnet
2. Configure the card to accept jumbo UDP frames

In order to do this, you need to:

1. Run ``ifconfig`` and note the MAC addresses of the NIC card (more on
   this below)
2. Place a file named ``02-static-ip.yaml`` under ``/etc/netplan``
3. Reboot

The contents of ``/etc/netplan/02-static-ip.yaml`` should be the
following:

.. code-block:: yaml

   # Setup the static IP and ETH config for the NIC card
   network:
     version: 2
     renderer: NetworkManager
     ethernets:
   ######################################
       eth1:
         set-name: eth1
         match:
           macaddress: 00:0f:53:51:76:40
         addresses: [192.168.2.1/24]
         optional: true
   #      mtu: 1500
         mtu: 9000
         dhcp4: false
   ######################################
       eth2:
         set-name: eth2
         match:
           macaddress: 00:0f:53:51:76:41
         addresses: [10.0.0.1/24]
         optional: true
         mtu: 1500
         dhcp4: false
   ######################################

Notes:

1. ``eth1`` and ``eth2`` are names given by the user to the two NIC card
   interfaces. The given card has two (2) SFP+ ports. ``eth1`` corresponds
   to the one farther away from the motherboard connection, ``eth2`` is the
   one closer to the motherboard connection. It is assumed that the one
   populated with the SFP transceiver is ``eth1``.
2. ``macaddress: 00:0f:53:51:76:40`` and ``00:0f:53:51:76:41`` are not
   random: they should be the same as the ones of the NIC card. You can
   deduce the values of the addresses by running ``ifconfig`` prior to
   editing the file. By running ``ifconfig`` on an un-configured NIC card,
   the server displays the default interface names for the two ports, plus
   their MAC addresses. These addresses should match the ones in the
   ``.yaml``.
3. The IP addresses (``addresses``) should be on the same subnet as the
   KCU105 firmware. Note that since we are only using ``eth1``, only that
   interface has been put on that subnet.
4. The jumbo frame configuration is associated with the ``mtu`` field.
   A value of ``9000`` allows the NIC card to accept jumbo frames.
