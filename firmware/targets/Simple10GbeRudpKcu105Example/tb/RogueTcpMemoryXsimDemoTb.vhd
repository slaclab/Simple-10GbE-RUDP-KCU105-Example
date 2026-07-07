-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: AxiVersion ScratchPad write-readback demo testbench for
--              RogueTcpMemoryWrap Vivado xsim co-simulation. The wrapper's
--              AXI-Lite master ports drive a surf.AxiVersion slave so a
--              single Rogue-side memory transaction (TcpClient ->
--              AxiVersion.ScratchPad) exercises both the write and read
--              AXI-Lite channels through one RogueTcpMemoryWrap instance.
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
use surf.AxiLitePkg.all;

library ruckus;
use ruckus.BuildInfoPkg.all;

entity RogueTcpMemoryXsimDemoTb is end RogueTcpMemoryXsimDemoTb;

architecture testbed of RogueTcpMemoryXsimDemoTb is

   constant TPD_C : time := 1 ns;

   -- Must match PORT_NUM in software/scripts/axiVersionMemoryDemo.py
   -- (distinct from the Stream demo's 9000)
   constant PORT_NUM_C : natural := 9100;

   -- Force a known, non-zero githash into BUILD_INFO_G so the demo's
   -- GitHash read path is observable regardless of build-time git state --
   -- same idiom as surf's AxiVersionTb.vhd.
   constant GET_BUILD_INFO_C : BuildInfoRetType := toBuildInfo(BUILD_INFO_C);
   constant MOD_BUILD_INFO_C : BuildInfoRetType := (
      buildString => GET_BUILD_INFO_C.buildString,
      fwVersion   => GET_BUILD_INFO_C.fwVersion,
      gitHash     => x"1111_2222_3333_4444_5555_6666_7777_8888_9999_AAAA");  -- Force githash
   constant SIM_BUILD_INFO_C : slv(2239 downto 0) := toSlv(MOD_BUILD_INFO_C);

   signal axilClk : sl := '0';
   signal axilRst : sl := '1';

   signal axilReadMaster  : AxiLiteReadMasterType;
   signal axilReadSlave   : AxiLiteReadSlaveType;
   signal axilWriteMaster : AxiLiteWriteMasterType;
   signal axilWriteSlave  : AxiLiteWriteSlaveType;

   -- Waveform-friendly aliases for the GUI demo
   signal araddr  : slv(31 downto 0);
   signal awaddr  : slv(31 downto 0);
   signal wdata   : slv(31 downto 0);
   signal rdata   : slv(31 downto 0);
   signal arvalid : sl;
   signal awvalid : sl;
   signal wvalid  : sl;
   signal rvalid  : sl;

begin

   U_ClkRst : entity surf.ClkRst
      generic map (
         CLK_PERIOD_G      => 10 ns,
         RST_START_DELAY_G => 0 ns,
         RST_HOLD_TIME_G   => 100 ns)
      port map (
         clkP => axilClk,
         rst  => axilRst);

   U_RogueTcpMemoryWrap : entity surf.RogueTcpMemoryWrap
      generic map (
         TPD_G      => TPD_C,
         PORT_NUM_G => PORT_NUM_C)
      port map (
         axilClk         => axilClk,
         axilRst         => axilRst,
         axilReadMaster  => axilReadMaster,
         axilReadSlave   => axilReadSlave,
         axilWriteMaster => axilWriteMaster,
         axilWriteSlave  => axilWriteSlave);

   U_DUT : entity surf.AxiVersion
      generic map (
         TPD_G        => TPD_C,
         BUILD_INFO_G => SIM_BUILD_INFO_C)
      port map (
         -- AXI-Lite Interface
         axiClk         => axilClk,
         axiRst         => axilRst,
         axiReadMaster  => axilReadMaster,
         axiReadSlave   => axilReadSlave,
         axiWriteMaster => axilWriteMaster,
         axiWriteSlave  => axilWriteSlave,
         -- Optional outputs left open
         userReset      => open,
         fpgaReload     => open,
         fpgaReloadAddr => open,
         upTimeCnt      => open,
         dnaValueOut    => open,
         fdValueOut     => open);

   araddr  <= axilReadMaster.araddr;
   awaddr  <= axilWriteMaster.awaddr;
   wdata   <= axilWriteMaster.wdata;
   rdata   <= axilReadSlave.rdata;
   arvalid <= axilReadMaster.arvalid;
   awvalid <= axilWriteMaster.awvalid;
   wvalid  <= axilWriteMaster.wvalid;
   rvalid  <= axilReadSlave.rvalid;

end testbed;
