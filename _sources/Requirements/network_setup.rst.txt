.. _requirements_network_setup:

=============
Network Setup
=============

The default configuration for the firmware is no DHCP for IP address
assignment and static IP address of 192.168.2.10.  You will need
to configure your network interface to be on the 192.168.2.XXX subnet:

.. code-block:: bash

   $ ip addr show <Network_Interface>
   <Network_Interface>: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 9000 qdisc mq state UP group default qlen 1000
       link/ether 00:1b:21:bd:40:22 brd ff:ff:ff:ff:ff:ff
       inet 192.168.2.1/24 brd 192.168.2.255 scope global noprefixroute <Network_Interface>
          valid_lft forever preferred_lft forever

The RUDP streaming interface uses **JUMBO** Ethernet frames.
You will need to make sure that you configure your network interface
to enable jumbo frame support.  If your RUDP Ethernet traffic goes through
any Ethernet switches or routers, you will need to enable jubmo frame
support for those devices as well.

.. code-block:: bash

  $ sudo ip link set dev <Network_Interface> mtu 9000
