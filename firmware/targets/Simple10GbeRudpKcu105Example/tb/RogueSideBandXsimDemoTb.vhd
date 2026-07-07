-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Bidirectional opcode/remData demo testbench for
--              RogueSideBandWrap Vivado xsim co-simulation. A tx-side
--              stimulus process pulses txOpCodeEn/txOpCode/txRemData after
--              reset deasserts; the driver script (sideBandDemo.py) asserts
--              on the tx frame and separately sends an rx* frame so both
--              marshalling directions are exercised through one
--              RogueSideBandWrap instance.
-------------------------------------------------------------------------------
-- This file is part of 'Simple-10GbE-RUDP-KCU105-Example'.
-- It is subject to the license terms in the LICENSE.txt file found in the
-- top-level directory of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of 'Simple-10GbE-RUDP-KCU105-Example', including this file, may be
-- copied, modified, propagated, or distributed except according to the terms
-- contained in the LICENSE.txt file.
-------------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;

library surf;
use surf.StdRtlPkg.all;

entity RogueSideBandXsimDemoTb is end RogueSideBandXsimDemoTb;

architecture testbed of RogueSideBandXsimDemoTb is

   constant TPD_C : time := 1 ns;

   -- Must match PORT_NUM in software/scripts/sideBandDemo.py
   -- (distinct from the Stream demo's 9000 and the Memory demo's 9100)
   constant PORT_NUM_C : natural := 9200;

   -- Tx stimulus values driven by this TB; sideBandDemo.py asserts on these
   -- exact values when it receives the tx frame.
   constant TX_OPCODE_C  : slv(7 downto 0) := x"3C";
   constant TX_REMDATA_C : slv(7 downto 0) := x"81";

   -- Interval between tx stimulus pulses
   constant TX_PERIOD_C : time := 1 us;

   signal axisClk : sl := '0';
   signal axisRst : sl := '1';

   -- tx* (TB-driven stimulus) / rx* (driven by the DPI backend from the
   -- driver script's rx frame) -- waveform-friendly signals for the GUI demo
   signal txOpCode   : slv(7 downto 0) := (others => '0');
   signal txOpCodeEn : sl              := '0';
   signal txRemData  : slv(7 downto 0) := (others => '0');
   signal rxOpCode   : slv(7 downto 0);
   signal rxOpCodeEn : sl;
   signal rxRemData  : slv(7 downto 0);

begin

   U_ClkRst : entity surf.ClkRst
      generic map (
         CLK_PERIOD_G      => 10 ns,
         RST_START_DELAY_G => 0 ns,
         RST_HOLD_TIME_G   => 100 ns)
      port map (
         clkP => axisClk,
         rst  => axisRst);

   U_RogueSideBandWrap : entity surf.RogueSideBandWrap
      generic map (
         TPD_G      => TPD_C,
         PORT_NUM_G => PORT_NUM_C)
      port map (
         sysClk     => axisClk,
         sysRst     => axisRst,
         txOpCode   => txOpCode,
         txOpCodeEn => txOpCodeEn,
         txRemData  => txRemData,
         rxOpCode   => rxOpCode,
         rxOpCodeEn => rxOpCodeEn,
         rxRemData  => rxRemData);

   -- New tx-side stimulus process (no analog in the Stream/Memory demos,
   -- which use pure loopback wiring instead of an internal stimulus
   -- generator): after reset deasserts, pulse txOpCodeEn for one clock while
   -- driving txOpCode/txRemData to the fixed values sideBandDemo.py asserts
   -- on, then repeat every TX_PERIOD_C so the demo stays observable for as
   -- long as the simulation runs. rxOpCode/rxOpCodeEn/rxRemData need no
   -- internal wiring -- the driver script sources them into the waveform via
   -- the DPI backend.
   STIM : process is
   begin
      txOpCode   <= (others => '0');
      txOpCodeEn <= '0';
      txRemData  <= (others => '0');

      wait until axisRst = '0';
      wait until rising_edge(axisClk);

      loop
         wait for TX_PERIOD_C;
         wait until rising_edge(axisClk);
         txOpCode   <= TX_OPCODE_C;
         txOpCodeEn <= '1';
         txRemData  <= TX_REMDATA_C;
         wait until rising_edge(axisClk);
         txOpCodeEn <= '0';
      end loop;

   end process STIM;

end testbed;
