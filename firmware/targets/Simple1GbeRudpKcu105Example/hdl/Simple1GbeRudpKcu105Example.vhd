-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Simple 1000baseX/Full Example
-------------------------------------------------------------------------------
-- This file is part of 'Simple-10GbE-RUDP-KCU105-Example'.
-- It is subject to the license terms in the LICENSE.txt file found in the
-- top-level directory of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of 'Simple-10GbE-RUDP-KCU105-Example', including this file,
-- may be copied, modified, propagated, or distributed except according to
-- the terms contained in the LICENSE.txt file.
-------------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.AxiLitePkg.all;

library work;
use work.CorePkg.all;

entity Simple1GbeRudpKcu105Example is
   generic (
      TPD_G        : time             := 1 ns;
      BUILD_INFO_G : BuildInfoType;
      SIMULATION_G : boolean          := false;
      IP_ADDR_G    : slv(31 downto 0) := x"0A02A8C0";  -- 192.168.2.10
      DHCP_G       : boolean          := false);
   port (
      -- I2C Ports
      sfpTxDisL  : out   sl;
      i2cRstL    : out   sl;
      i2cScl     : inout sl;
      i2cSda     : inout sl;
      -- XADC Ports
      vPIn       : in    sl;
      vNIn       : in    sl;
      -- System Ports
      emcClk     : in    sl;
      extRst     : in    sl;
      sysClk300P : in    sl;
      sysClk300N : in    sl;
      led        : out   slv(7 downto 0);
      -- Boot Memory Ports
      flashCsL   : out   sl;
      flashMosi  : out   sl;
      flashMiso  : in    sl;
      flashHoldL : out   sl;
      flashWp    : out   sl;
      -- SFP ETH Ports
      ethClkP    : in    sl;
      ethClkN    : in    sl;
      ethRxP     : in    sl;
      ethRxN     : in    sl;
      ethTxP     : out   sl;
      ethTxN     : out   sl;
      -- RJ45 ETH Ports
      phyClkP    : in    sl;
      phyClkN    : in    sl;
      phyRxP     : in    sl;
      phyRxN     : in    sl;
      phyTxP     : out   sl;
      phyTxN     : out   sl;
      phyMdc     : out   sl;
      phyMdio    : inout sl;
      phyRstN    : out   sl;
      phyIrqN    : in    sl;
      -- PGP Serial Ports
      pgpClkP    : in    sl;
      pgpClkN    : in    sl;
      pgpRxP     : in    slv(3 downto 0);
      pgpRxN     : in    slv(3 downto 0);
      pgpTxP     : out   slv(3 downto 0);
      pgpTxN     : out   slv(3 downto 0));
end Simple1GbeRudpKcu105Example;

architecture top_level of Simple1GbeRudpKcu105Example is

   signal heartbeat  : sl;
   signal phyReady   : sl;
   signal rssiLinkUp : slv(1 downto 0);

   -- Clock and Reset
   signal axilClk : sl;
   signal axilRst : sl;

   -- AXI-Stream: Stream Interface
   signal ibRudpMaster : AxiStreamMasterType;
   signal ibRudpSlave  : AxiStreamSlaveType;
   signal obRudpMaster : AxiStreamMasterType;
   signal obRudpSlave  : AxiStreamSlaveType;

   -- AXI-Lite: Register Access
   signal axilReadMaster  : AxiLiteReadMasterType;
   signal axilReadSlave   : AxiLiteReadSlaveType;
   signal axilWriteMaster : AxiLiteWriteMasterType;
   signal axilWriteSlave  : AxiLiteWriteSlaveType;
   
   -- LED signal passed from App
    signal appLedOut      : slv(1 downto 0);

begin

   led(7 downto 6) <= appLedOut;
   led(5) <= heartbeat; 
   led(4) <= axilRst;
   led(3) <= not(axilRst);
   led(2) <= rssiLinkUp(1);
   led(1) <= rssiLinkUp(0);
   led(0) <= phyReady;

   -----------------------
   -- Core Firmware Module
   -----------------------
   U_Core : entity work.Core
      generic map (
         TPD_G        => TPD_G,
         BUILD_INFO_G => BUILD_INFO_G,
         SIMULATION_G => SIMULATION_G,
         ETH_BUILD_G  => SFP_1G_C,
         IP_ADDR_G    => IP_ADDR_G,
         DHCP_G       => DHCP_G)
      port map (
         -- Clock and Reset
         axilClk         => axilClk,
         axilRst         => axilRst,
         -- AXI-Stream Interface
         ibRudpMaster    => ibRudpMaster,
         ibRudpSlave     => ibRudpSlave,
         obRudpMaster    => obRudpMaster,
         obRudpSlave     => obRudpSlave,
         -- AXI-Lite Interface
         axilReadMaster  => axilReadMaster,
         axilReadSlave   => axilReadSlave,
         axilWriteMaster => axilWriteMaster,
         axilWriteSlave  => axilWriteSlave,
         -- I2C Ports
         sfpTxDisL       => sfpTxDisL,
         i2cRstL         => i2cRstL,
         i2cScl          => i2cScl,
         i2cSda          => i2cSda,
         -- SYSMON Ports
         vPIn            => vPIn,
         vNIn            => vNIn,
         -- System Ports
         extRst          => extRst,
         sysClk300P      => sysClk300P,
         sysClk300N      => sysClk300N,
         emcClk          => emcClk,
         heartbeat       => heartbeat,
         phyReady        => phyReady,
         rssiLinkUp      => rssiLinkUp,
         -- Boot Memory Ports
         flashCsL        => flashCsL,
         flashMosi       => flashMosi,
         flashMiso       => flashMiso,
         flashHoldL      => flashHoldL,
         flashWp         => flashWp,
         -- SFP ETH Ports
         ethClkP         => ethClkP,
         ethClkN         => ethClkN,
         ethRxP          => ethRxP,
         ethRxN          => ethRxN,
         ethTxP          => ethTxP,
         ethTxN          => ethTxN,
         -- RJ45 ETH Ports
         phyClkP         => phyClkP,
         phyClkN         => phyClkN,
         phyRxP          => phyRxP,
         phyRxN          => phyRxN,
         phyTxP          => phyTxP,
         phyTxN          => phyTxN,
         phyMdc          => phyMdc,
         phyMdio         => phyMdio,
         phyRstN         => phyRstN,
         phyIrqN         => phyIrqN);

   ------------------------------
   -- Application Firmware Module
   ------------------------------
   U_App : entity work.App
      generic map (
         TPD_G        => TPD_G,
         SIMULATION_G => SIMULATION_G)
      port map (
         -- Clock and Reset
         axilClk         => axilClk,
         axilRst         => axilRst,
         -- AXI-Stream Interface
         ibRudpMaster    => ibRudpMaster,
         ibRudpSlave     => ibRudpSlave,
         obRudpMaster    => obRudpMaster,
         obRudpSlave     => obRudpSlave,
         -- AXI-Lite Interface
         axilReadMaster  => axilReadMaster,
         axilReadSlave   => axilReadSlave,
         axilWriteMaster => axilWriteMaster,
         axilWriteSlave  => axilWriteSlave,
         -- LED Output Port
         led_o           => appLedOut,
          -- PGP Serial Ports
         pgpClkP         => pgpClkP,
         pgpClkN         => pgpClkN,
         pgpRxP          => pgpRxP,
         pgpRxN          => pgpRxN,
         pgpTxP          => pgpTxP,
         pgpTxN          => pgpTxN);

end top_level;
