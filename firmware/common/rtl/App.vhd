-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Application Top-Level Firmware Module
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

entity App is
   generic (
      TPD_G        : time    := 1 ns;
      SIMULATION_G : boolean := false);
   port (
      -- Clock and Reset
      axilClk         : in  sl;
      axilRst         : in  sl;
      -- AXI-Stream Interface
      ibRudpMaster    : out AxiStreamMasterType;
      ibRudpSlave     : in  AxiStreamSlaveType;
      obRudpMaster    : in  AxiStreamMasterType;
      obRudpSlave     : out AxiStreamSlaveType;
      -- AXI-Lite Interface
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType);
end App;

architecture mapping of App is

   constant TX_INDEX_C  : natural := 0;
   constant MEM_INDEX_C : natural := 1;

   constant NUM_AXIL_MASTERS_C : positive := 2;

   constant XBAR_CONFIG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := genAxiLiteConfig(NUM_AXIL_MASTERS_C, x"8000_0000", 20, 16);

   signal axilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal axilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0) := (others => AXI_LITE_WRITE_SLAVE_EMPTY_SLVERR_C);
   signal axilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal axilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0)  := (others => AXI_LITE_READ_SLAVE_EMPTY_SLVERR_C);

begin

   -------------------------------
   -- Terminating unused RX stream
   -------------------------------
   obRudpSlave <= AXI_STREAM_SLAVE_FORCE_C;

   ---------------------------
   -- AXI-Lite Crossbar Module
   ---------------------------
   U_XBAR : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
         MASTERS_CONFIG_G   => XBAR_CONFIG_C)
      port map (
         sAxiWriteMasters(0) => axilWriteMaster,
         sAxiWriteSlaves(0)  => axilWriteSlave,
         sAxiReadMasters(0)  => axilReadMaster,
         sAxiReadSlaves(0)   => axilReadSlave,
         mAxiWriteMasters    => axilWriteMasters,
         mAxiWriteSlaves     => axilWriteSlaves,
         mAxiReadMasters     => axilReadMasters,
         mAxiReadSlaves      => axilReadSlaves,
         axiClk              => axilClk,
         axiClkRst           => axilRst);

   --------------------------------
   -- Application TX Streaming Module
   --------------------------------
   U_AppTx : entity work.AppTx
      generic map (
         TPD_G        => TPD_G,
         SIMULATION_G => SIMULATION_G)
      port map (
         -- Clock and Reset
         axilClk         => axilClk,
         axilRst         => axilRst,
         -- AXI-Stream Interface
         txMaster        => ibRudpMaster,
         txSlave         => ibRudpSlave,
         -- AXI-Lite Interface
         axilReadMaster  => axilReadMasters(TX_INDEX_C),
         axilReadSlave   => axilReadSlaves(TX_INDEX_C),
         axilWriteMaster => axilWriteMasters(TX_INDEX_C),
         axilWriteSlave  => axilWriteSlaves(TX_INDEX_C));

   --------------------------------
   -- AXI-Lite General Memory Module
   --------------------------------
   U_Mem : entity surf.AxiDualPortRam
      generic map (
         TPD_G        => TPD_G,
         COMMON_CLK_G => true,
         ADDR_WIDTH_G => 10,
         DATA_WIDTH_G => 32)
      port map (
         -- AXI-Lite Interface
         axiClk         => axilClk,
         axiRst         => axilRst,
         axiReadMaster  => axilReadMasters(MEM_INDEX_C),
         axiReadSlave   => axilReadSlaves(MEM_INDEX_C),
         axiWriteMaster => axilWriteMasters(MEM_INDEX_C),
         axiWriteSlave  => axilWriteSlaves(MEM_INDEX_C));

end mapping;
