-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Simulation test bed for FPGA FW/SW co-simulation
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
use ieee.std_logic_arith.all;
use ieee.std_logic_unsigned.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.SsiPkg.all;

library ruckus;
use ruckus.BuildInfoPkg.all;

entity SimpleRj45RudpKcu105ExampleTb is end SimpleRj45RudpKcu105ExampleTb;

architecture testbed of SimpleRj45RudpKcu105ExampleTb is

   constant GET_BUILD_INFO_C : BuildInfoRetType := toBuildInfo(BUILD_INFO_C);
   constant MOD_BUILD_INFO_C : BuildInfoRetType := (
      buildString => GET_BUILD_INFO_C.buildString,
      fwVersion   => GET_BUILD_INFO_C.fwVersion,
      gitHash     => x"1111_2222_3333_4444_5555_6666_7777_8888_9999_AAAA");  -- Force githash for simulation testing
   constant SIM_BUILD_INFO_C : slv(2239 downto 0) := toSlv(MOD_BUILD_INFO_C);

begin

   U_Fpga : entity work.SimpleRj45RudpKcu105Example
      generic map (
         SIMULATION_G => true,
         BUILD_INFO_G => SIM_BUILD_INFO_C)
      port map (
         -- I2C Ports
         sfpTxDisL  => open,
         i2cRstL    => open,
         i2cScl     => open,
         i2cSda     => open,
         -- XADC Ports
         vPIn       => '0',
         vNIn       => '1',
         -- System Ports
         emcClk     => '0',
         sysClk300P => '0',
         sysClk300N => '1',
         extRst     => '0',
         led        => open,
         -- Boot Memory Ports
         flashCsL   => open,
         flashMosi  => open,
         flashMiso  => '1',
         flashHoldL => open,
         flashWp    => open,
         -- SFP ETH Ports
         ethClkP    => '0',
         ethClkN    => '1',
         ethRxP     => '0',
         ethRxN     => '1',
         ethTxP     => open,
         ethTxN     => open,
         -- RJ45 ETH Ports
         phyClkP    => '0',
         phyClkN    => '1',
         phyRxP     => '0',
         phyRxN     => '1',
         phyTxP     => open,
         phyTxN     => open,
         phyMdc     => open,
         phyMdio    => open,
         phyRstN    => open,
         phyIrqN    => '1');

end testbed;
