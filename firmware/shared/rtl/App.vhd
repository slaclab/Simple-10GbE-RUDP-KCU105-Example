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
use surf.Pgp4Pkg.all;
use ieee.numeric_std.all;

entity App is
   generic (
      TPD_G        : time    := 1 ns;
      SIMULATION_G : boolean := false;
      EN_PGP_MON_G : boolean := true;
      EN_GTH_DRP_G : boolean := true;
      EN_QPLL_DRP_G : boolean := true);
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
      axilWriteSlave  : out AxiLiteWriteSlaveType;
      -- LED Output Port
      led_o           : out slv(1 downto 0);
      -- PGP Serial Ports
      pgpClkP         : in  sl;
      pgpClkN         : in  sl;
      pgpRxP          : in  slv(0 downto 0);
      pgpRxN          : in  slv(0 downto 0);
      pgpTxP          : out slv(0 downto 0);
      pgpTxN          : out slv(0 downto 0));
      
end App;

architecture mapping of App is

   constant TX_INDEX_C  : natural := 0;
   constant MEM_INDEX_C : natural := 1;
   constant PGP_INDEX_C : natural := 2;
   
   constant NUM_AXIL_MASTERS_C : positive := 3;

   constant XBAR_CONFIG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := genAxiLiteConfig(NUM_AXIL_MASTERS_C, x"8000_0000", 20, 16);

   signal axilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal axilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0) := (others => AXI_LITE_WRITE_SLAVE_EMPTY_SLVERR_C);
   signal axilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal axilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0)  := (others => AXI_LITE_READ_SLAVE_EMPTY_SLVERR_C);
    
   -- PGP AXI-Stream Signals
   constant NUM_PGP_LANES_C : positive := 1;
   constant NUM_PGP_VCS_C   : positive := 1;
   signal pgpTxMasters_s    : AxiStreamMasterArray((NUM_PGP_LANES_C*NUM_PGP_VCS_C)-1 downto 0) := (others => AXI_STREAM_MASTER_INIT_C);
   signal pgpTxSlaves_s     : AxiStreamSlaveArray((NUM_PGP_LANES_C*NUM_PGP_VCS_C)-1 downto 0);
   signal pgpRxMasters_s    : AxiStreamMasterArray((NUM_PGP_LANES_C*NUM_PGP_VCS_C)-1 downto 0);
   signal pgpRxSlaves_s     : AxiStreamSlaveArray((NUM_PGP_LANES_C*NUM_PGP_VCS_C)-1 downto 0) := (others => AXI_STREAM_SLAVE_FORCE_C);

   -- Constants and signals for unused Non-VC ports
   constant PGP4_RX_IN_C      : Pgp4RxInArray(NUM_PGP_LANES_C-1 downto 0)      := (others => PGP4_RX_IN_INIT_C);
   constant PGP4_TX_IN_C      : Pgp4TxInArray(NUM_PGP_LANES_C-1 downto 0)      := (others => PGP4_TX_IN_INIT_C);
   constant AXI_STREAM_CTRL_C : AxiStreamCtrlArray((NUM_PGP_LANES_C*NUM_PGP_VCS_C)-1 downto 0) := (others => AXI_STREAM_CTRL_INIT_C);
   signal   pgpRxOut_s        : Pgp4RxOutArray(NUM_PGP_LANES_C-1 downto 0);
   signal   pgpTxOut_s        : Pgp4TxOutArray(NUM_PGP_LANES_C-1 downto 0);
   signal   pgpClk_s          : slv(NUM_PGP_LANES_C-1 downto 0);
   signal   pgpClkRst_s       : slv(NUM_PGP_LANES_C-1 downto 0);

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
         axilWriteSlave  => axilWriteSlaves(TX_INDEX_C),
         led_out         => led_o);

   --------------------------------
   -- AXI-Lite General Memory Module
   --------------------------------
   U_Mem : entity surf.AxiDualPortRam
      generic map (
         TPD_G        => TPD_G,
         COMMON_CLK_G => true,
         SYNTH_MODE_G => "xpm",
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
         
   -----------------------------------------------------------------
   -- PGPv4 GTH Wrapper
   -----------------------------------------------------------------
   U_PgpWrapper : entity surf.Pgp4GthUsWrapper
      generic map(
         TPD_G             => TPD_G,
         NUM_LANES_G       => NUM_PGP_LANES_C,
         NUM_VC_G          => NUM_PGP_VCS_C,
         RATE_G            => "6.25Gbps", -- Or "6.25Gbps", "3.125Gbps" CHANGED FROM 10.3125 for our case
         REFCLK_FREQ_G     => 156.25E+6,
         AXIL_CLK_FREQ_G   => 125.0E+6, -- Assumes axilClk is 125MHz
         EN_PGP_MON_G    => EN_PGP_MON_G,
         EN_GTH_DRP_G    => EN_GTH_DRP_G,
         EN_QPLL_DRP_G   => EN_QPLL_DRP_G)      
      port map(
         -- Stable Clock and Reset
         stableClk         => axilClk,
         stableRst         => axilRst,
         -- Gt Serial IO
         pgpGtTxP          => pgpTxP,
         pgpGtTxN          => pgpTxN,
         pgpGtRxP          => pgpRxP,
         pgpGtRxN          => pgpRxN,
         -- GT Clocking
         pgpRefClkP        => pgpClkP,
         pgpRefClkN        => pgpClkN,
         pgpRefClkOut      => open,          -- Unused output
         pgpRefClkDiv2Bufg => open,          -- Unused output
         -- PGP Core Clocking
         pgpClk            => pgpClk_s,      -- Unused output
         pgpClkRst         => pgpClkRst_s,   -- Unused output
         -- Rx/Tx I/O
         pgpRxIn           => PGP4_RX_IN_C,
         pgpRxOut          => pgpRxOut_s,
         pgpTxIn           => PGP4_TX_IN_C,
         pgpTxOut          => pgpTxOut_s,
         -- Frame Transmit Interface
         pgpTxMasters      => pgpTxMasters_s,
         pgpTxSlaves       => pgpTxSlaves_s,
         -- Frame Receive Interface
         pgpRxMasters      => pgpRxMasters_s,
--         pgpRxSlaves       => AXI_STREAM_SLAVE_FORCE_C,
         pgpRxSlaves       => pgpRxSlaves_s,
         pgpRxCtrl         => AXI_STREAM_CTRL_C, -- Connect to constant default
         -- AXI-Lite Register Interface (axilClk domain)
         axilClk           => axilClk,
         axilRst           => axilRst,
         axilReadMaster    => axilReadMasters(PGP_INDEX_C),
         axilReadSlave     => axilReadSlaves(PGP_INDEX_C),
         axilWriteMaster   => axilWriteMasters(PGP_INDEX_C),
         axilWriteSlave    => axilWriteSlaves(PGP_INDEX_C));
        
end mapping;
