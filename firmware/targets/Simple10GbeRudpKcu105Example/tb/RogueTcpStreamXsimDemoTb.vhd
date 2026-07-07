-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: PRBS loopback demo testbench for RogueTcpStreamWrap Vivado
--              xsim co-simulation. Loops the wrapper's AXI-Stream master
--              output back into its own slave input so a single Rogue-side
--              PRBS action (PrbsTx -> TcpClient -> PrbsRx) exercises both
--              directions through one RogueTcpStreamWrap instance.
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
use surf.AxiStreamPkg.all;
use surf.SsiPkg.all;

entity RogueTcpStreamXsimDemoTb is end RogueTcpStreamXsimDemoTb;

architecture testbed of RogueTcpStreamXsimDemoTb is

   constant TPD_C : time := 1 ns;

   -- Must match PORT_NUM in software/scripts/prbsLoopbackDemo.py
   constant PORT_NUM_C : natural := 9000;

   constant AXIS_CONFIG_C : AxiStreamConfigType := ssiAxiStreamConfig(8);

   signal axisClk : sl := '0';
   signal axisRst : sl := '1';

   -- Loopback net: RogueTcpStreamWrap's mAxis (Rogue peer -> FPGA) is fed
   -- straight back into its own sAxis (FPGA -> Rogue peer).
   signal loopMaster : AxiStreamMasterType;
   signal loopSlave  : AxiStreamSlaveType;

   -- Waveform-friendly aliases for the GUI demo
   signal loopValid : sl;
   signal loopData  : slv(63 downto 0);
   signal loopLast  : sl;

begin

   U_ClkRst : entity surf.ClkRst
      generic map (
         CLK_PERIOD_G      => 10 ns,
         RST_START_DELAY_G => 0 ns,
         RST_HOLD_TIME_G   => 100 ns)
      port map (
         clkP => axisClk,
         rst  => axisRst);

   U_RogueTcpStreamWrap : entity surf.RogueTcpStreamWrap
      generic map (
         TPD_G         => TPD_C,
         PORT_NUM_G    => PORT_NUM_C,
         SSI_EN_G      => true,
         CHAN_COUNT_G  => 1,
         AXIS_CONFIG_G => AXIS_CONFIG_C)
      port map (
         axisClk     => axisClk,
         axisRst     => axisRst,
         -- Loopback: mAxis -> sAxis, sAxisSlave -> mAxisSlave
         sAxisMaster => loopMaster,
         sAxisSlave  => loopSlave,
         mAxisMaster => loopMaster,
         mAxisSlave  => loopSlave);

   loopValid <= loopMaster.tValid;
   loopData  <= loopMaster.tData(63 downto 0);
   loopLast  <= loopMaster.tLast;

end testbed;
