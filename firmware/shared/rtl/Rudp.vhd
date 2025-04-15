-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: RUDP Firmware Module
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
use surf.EthMacPkg.all;
use surf.RssiPkg.all;

library unisim;
use unisim.vcomponents.all;

entity Rudp is
   generic (
      TPD_G            : time := 1 ns;
      BUILD_10G_G      : boolean;
      IP_ADDR_G        : slv(31 downto 0);
      DHCP_G           : boolean;
      AXIL_BASE_ADDR_G : slv(31 downto 0));
   port (
      -- System Ports
      extRst           : in  sl;
      -- Ethernet Status
      phyReady         : out sl;
      rssiLinkUp       : out slv(1 downto 0);
      -- Clock and Reset
      axilClk          : out sl;
      axilRst          : out sl;
      -- AXI-Stream Interface
      ibRudpMaster     : in  AxiStreamMasterType;
      ibRudpSlave      : out AxiStreamSlaveType;
      obRudpMaster     : out AxiStreamMasterType;
      obRudpSlave      : in  AxiStreamSlaveType;
      -- Master AXI-Lite Interface
      mAxilReadMaster  : out AxiLiteReadMasterType;
      mAxilReadSlave   : in  AxiLiteReadSlaveType;
      mAxilWriteMaster : out AxiLiteWriteMasterType;
      mAxilWriteSlave  : in  AxiLiteWriteSlaveType;
      -- Slave AXI-Lite Interfaces
      sAxilReadMaster  : in  AxiLiteReadMasterType;
      sAxilReadSlave   : out AxiLiteReadSlaveType;
      sAxilWriteMaster : in  AxiLiteWriteMasterType;
      sAxilWriteSlave  : out AxiLiteWriteSlaveType;
      -- ETH GT Pins
      ethClkP          : in  sl;
      ethClkN          : in  sl;
      ethRxP           : in  sl;
      ethRxN           : in  sl;
      ethTxP           : out sl;
      ethTxN           : out sl);
end Rudp;

architecture mapping of Rudp is

   constant PHY_INDEX_C      : natural := 0;
   constant UDP_INDEX_C      : natural := 1;
   constant RSSI_INDEX_C     : natural := 2;  -- 2:3
   constant AXIS_MON_INDEX_C : natural := 4;

   constant NUM_AXIL_MASTERS_C : positive := 5;

   constant XBAR_CONFIG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := genAxiLiteConfig(NUM_AXIL_MASTERS_C, AXIL_BASE_ADDR_G, 20, 16);

   signal axilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal axilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0) := (others => AXI_LITE_WRITE_SLAVE_EMPTY_SLVERR_C);
   signal axilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal axilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0)  := (others => AXI_LITE_READ_SLAVE_EMPTY_SLVERR_C);

   constant CLK_FREQUENCY_C : real := ite(BUILD_10G_G, 156.25E+6, 125.0E+6);

   -- UDP constants
   constant UDP_SRV_SRP_IDX_C  : natural  := 0;
   constant UDP_SRV_DATA_IDX_C : natural  := 1;
   constant UDP_SRV_XVC_IDX_C  : natural  := 2;
   constant SERVER_SIZE_C      : positive := 3;
   constant SERVER_PORTS_C : PositiveArray(SERVER_SIZE_C-1 downto 0) := (
      UDP_SRV_SRP_IDX_C  => 8192,       -- SRPv3
      UDP_SRV_DATA_IDX_C => 8193,       -- Streaming data
      UDP_SRV_XVC_IDX_C  => 2542);      -- Xilinx XVC

   -- RSSI constants
   constant RSSI_SIZE_C : positive := 1;  -- Implementing only 1 VC per RSSI link
   constant AXIS_CONFIG_C : AxiStreamConfigArray(RSSI_SIZE_C-1 downto 0) := (
      0 => RSSI_AXIS_CONFIG_C);  -- Only using 64 bit AXI stream configuration

   signal ibMacMaster : AxiStreamMasterType;
   signal ibMacSlave  : AxiStreamSlaveType;
   signal obMacMaster : AxiStreamMasterType;
   signal obMacSlave  : AxiStreamSlaveType;

   signal obServerMasters : AxiStreamMasterArray(SERVER_SIZE_C-1 downto 0);
   signal obServerSlaves  : AxiStreamSlaveArray(SERVER_SIZE_C-1 downto 0);
   signal ibServerMasters : AxiStreamMasterArray(SERVER_SIZE_C-1 downto 0);
   signal ibServerSlaves  : AxiStreamSlaveArray(SERVER_SIZE_C-1 downto 0);

   -- One RSSI per UDP port (which is why SERVER_SIZE_C used instead of SERVER_SIZE_C)
   signal rssiIbMasters : AxiStreamMasterArray(SERVER_SIZE_C-1 downto 0);
   signal rssiIbSlaves  : AxiStreamSlaveArray(SERVER_SIZE_C-1 downto 0);
   signal rssiObMasters : AxiStreamMasterArray(SERVER_SIZE_C-1 downto 0);
   signal rssiObSlaves  : AxiStreamSlaveArray(SERVER_SIZE_C-1 downto 0);

   signal efuse    : slv(31 downto 0);
   signal localMac : slv(47 downto 0);
   signal localIp  : slv(31 downto 0);

   signal ethClk   : sl;
   signal ethRst   : sl;
   signal extReset : sl;
   signal refClk   : sl;

begin

   axilClk <= ethClk;
   axilRst <= ethRst;

   U_XBAR : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
         MASTERS_CONFIG_G   => XBAR_CONFIG_C)
      port map (
         axiClk              => ethClk,
         axiClkRst           => ethRst,
         sAxiWriteMasters(0) => sAxilWriteMaster,
         sAxiWriteSlaves(0)  => sAxilWriteSlave,
         sAxiReadMasters(0)  => sAxilReadMaster,
         sAxiReadSlaves(0)   => sAxilReadSlave,
         mAxiWriteMasters    => axilWriteMasters,
         mAxiWriteSlaves     => axilWriteSlaves,
         mAxiReadMasters     => axilReadMasters,
         mAxiReadSlaves      => axilReadSlaves);

   --------------------------------------------------
   -- Example of using EFUSE to store the MAC Address
   --------------------------------------------------
   U_EFuse : EFUSE_USR
      port map (
         EFUSEUSR => efuse);

   -------------------------------------
   -- 08:00:56:XX:XX:XX (big endian SLV)
   -------------------------------------
   localMac(23 downto 0)  <= x"56_00_08";  -- 08:00:56 is the SLAC Vendor ID
   localMac(47 downto 24) <= efuse(31 downto 8);

   -----------------------------------------------
   -- Default IP address before DHCP IP assignment
   -----------------------------------------------
   localIp <= IP_ADDR_G;

   -----------------
   -- Power Up Reset
   -----------------
   U_PwrUpRst : entity surf.PwrUpRst
      generic map (
         TPD_G      => TPD_G,
         DURATION_G => 156250000)
      port map (
         arst   => extRst,
         clk    => refClk,
         rstOut => extReset);

   GEN_10G : if (BUILD_10G_G = true) generate
      ----------------------------------
      -- 10 GigE PHY/MAC Ethernet Layers
      ----------------------------------
      U_10GigE : entity surf.TenGigEthGthUltraScaleWrapper
         generic map (
            TPD_G        => TPD_G,
            NUM_LANE_G   => 1,
            PAUSE_EN_G   => true,       -- Enable ETH pause
            EN_AXI_REG_G => true)       -- Enable diagnostic AXI-Lite interface
         port map (
            -- Local Configurations
            localMac(0)            => localMac,
            -- Streaming DMA Interface
            dmaClk(0)              => ethClk,
            dmaRst(0)              => ethRst,
            dmaIbMasters(0)        => obMacMaster,
            dmaIbSlaves(0)         => obMacSlave,
            dmaObMasters(0)        => ibMacMaster,
            dmaObSlaves(0)         => ibMacSlave,
            -- Slave AXI-Lite Interface
            axiLiteClk(0)          => ethClk,
            axiLiteRst(0)          => ethRst,
            axiLiteReadMasters(0)  => axilReadMasters(PHY_INDEX_C),
            axiLiteReadSlaves(0)   => axilReadSlaves(PHY_INDEX_C),
            axiLiteWriteMasters(0) => axilWriteMasters(PHY_INDEX_C),
            axiLiteWriteSlaves(0)  => axilWriteSlaves(PHY_INDEX_C),
            -- Misc. Signals
            extRst                 => extReset,
            coreClk                => ethClk,
            coreRst                => ethRst,
            phyReady(0)            => phyReady,
            -- MGT Clock Port 156.25 MHz
            gtClkP                 => ethClkP,
            gtClkN                 => ethClkN,
            -- MGT Ports
            gtTxP(0)               => ethTxP,
            gtTxN(0)               => ethTxN,
            gtRxP(0)               => ethRxP,
            gtRxN(0)               => ethRxN);
      refClk <= ethClk;
   end generate;

   GEN_1G : if (BUILD_10G_G = false) generate
      ----------------------------------
      -- 1 GigE PHY/MAC Ethernet Layers
      ----------------------------------
      U_1GigE : entity surf.GigEthGthUltraScaleWrapper
         generic map (
            TPD_G              => TPD_G,
            NUM_LANE_G         => 1,
            PAUSE_EN_G         => true,  -- Enable ETH pause
            EN_AXI_REG_G       => true,  -- Enable diagnostic AXI-Lite interface
            -- QUAD PLL Configurations
            USE_GTREFCLK_G     => false,
            CLKIN_PERIOD_G     => 6.4,  -- 156.25 MHz
            DIVCLK_DIVIDE_G    => 5,    -- 31.25 MHz = (156.25 MHz/5)
            CLKFBOUT_MULT_F_G  => 32.0,  -- 1 GHz = (32 x 31.25 MHz)
            CLKOUT0_DIVIDE_F_G => 8.0)  -- 125 MHz = (1.0 GHz/8)
         port map (
            -- Local Configurations
            localMac(0)            => localMac,
            -- Streaming DMA Interface
            dmaClk(0)              => ethClk,
            dmaRst(0)              => ethRst,
            dmaIbMasters(0)        => obMacMaster,
            dmaIbSlaves(0)         => obMacSlave,
            dmaObMasters(0)        => ibMacMaster,
            dmaObSlaves(0)         => ibMacSlave,
            -- Slave AXI-Lite Interface
            axiLiteClk(0)          => ethClk,
            axiLiteRst(0)          => ethRst,
            axiLiteReadMasters(0)  => axilReadMasters(PHY_INDEX_C),
            axiLiteReadSlaves(0)   => axilReadSlaves(PHY_INDEX_C),
            axiLiteWriteMasters(0) => axilWriteMasters(PHY_INDEX_C),
            axiLiteWriteSlaves(0)  => axilWriteSlaves(PHY_INDEX_C),
            -- Misc. Signals
            extRst                 => extReset,
            phyClk                 => ethClk,
            phyRst                 => ethRst,
            phyReady(0)            => phyReady,
            refClkOut              => refClk,
            -- MGT Clock Port
            gtClkP                 => ethClkP,
            gtClkN                 => ethClkN,
            -- MGT Ports
            gtTxP(0)               => ethTxP,
            gtTxN(0)               => ethTxN,
            gtRxP(0)               => ethRxP,
            gtRxN(0)               => ethRxN);
   end generate;

   ------------------------------------
   -- IPv4/ARP/UDP/DHCP Ethernet Layers
   ------------------------------------
   U_UDP : entity surf.UdpEngineWrapper
      generic map (
         -- Simulation Generics
         TPD_G          => TPD_G,
         -- UDP Server Generics
         SERVER_EN_G    => true,        -- UDP Server only
         SERVER_SIZE_G  => SERVER_SIZE_C,
         SERVER_PORTS_G => SERVER_PORTS_C,
         -- UDP Client Generics
         CLIENT_EN_G    => false,       -- UDP Server only
         -- General IPv4/ARP/DHCP Generics
         DHCP_G         => DHCP_G,
         CLK_FREQ_G     => CLK_FREQUENCY_C,
         COMM_TIMEOUT_G => 10)          -- Timeout used for ARP and DHCP
      port map (
         -- Local Configurations
         localMac        => localMac,
         localIp         => localIp,
         -- Interface to Ethernet Media Access Controller (MAC)
         obMacMaster     => obMacMaster,
         obMacSlave      => obMacSlave,
         ibMacMaster     => ibMacMaster,
         ibMacSlave      => ibMacSlave,
         -- Interface to UDP Server engine(s)
         obServerMasters => obServerMasters,
         obServerSlaves  => obServerSlaves,
         ibServerMasters => ibServerMasters,
         ibServerSlaves  => ibServerSlaves,
         -- AXI-Lite Interface
         axilReadMaster  => axilReadMasters(UDP_INDEX_C),
         axilReadSlave   => axilReadSlaves(UDP_INDEX_C),
         axilWriteMaster => axilWriteMasters(UDP_INDEX_C),
         axilWriteSlave  => axilWriteSlaves(UDP_INDEX_C),
         -- Clock and Reset
         clk             => ethClk,
         rst             => ethRst);

   -----------------------------------------------------------------
   -- Xilinx Virtual Cable (XVC)
   -- https://www.xilinx.com/products/intellectual-property/xvc.html
   -----------------------------------------------------------------
--   U_XVC : entity surf.UdpDebugBridgeWrapper
--      generic map (
--         TPD_G => TPD_G)
--      port map (
--         -- Clock and Reset
--         clk            => ethClk,
--         rst            => ethRst,
--         -- UDP XVC Interface
--         obServerMaster => obServerMasters(UDP_SRV_XVC_IDX_C),
--         obServerSlave  => obServerSlaves(UDP_SRV_XVC_IDX_C),
--         ibServerMaster => ibServerMasters(UDP_SRV_XVC_IDX_C),
--         ibServerSlave  => ibServerSlaves(UDP_SRV_XVC_IDX_C));
   U_DmaXvcWrapper : entity surf.DmaXvcWrapper  -- Using this project to regression test DmaXvcWrapper, we could of just used UdpDebugBridgeWrapper directly (see above) for this UDP application instead
      generic map (
         TPD_G             => TPD_G,
         DMA_AXIS_CONFIG_G => EMAC_AXIS_CONFIG_C)
      port map (
         -- 156.25MHz XVC Clock/Reset (xvcClk156 domain)
         xvcClk156   => ethClk,
         xvcRst156   => ethRst,
         -- DMA Interface (dmaClk domain)
         dmaClk      => ethClk,
         dmaRst      => ethRst,
         dmaObMaster => obServerMasters(UDP_SRV_XVC_IDX_C),
         dmaObSlave  => obServerSlaves(UDP_SRV_XVC_IDX_C),
         dmaIbMaster => ibServerMasters(UDP_SRV_XVC_IDX_C),
         dmaIbSlave  => ibServerSlaves(UDP_SRV_XVC_IDX_C));

   GEN_VEC :
   for i in 0 to 1 generate

      ------------------------------------------
      -- Software's RSSI Server Interface @ 8192
      ------------------------------------------
      U_RssiServer : entity surf.RssiCoreWrapper
         generic map (
            TPD_G              => TPD_G,
            PIPE_STAGES_G      => 1,
            SERVER_G           => true,
            APP_ILEAVE_EN_G    => true,
            MAX_SEG_SIZE_G     => ite(i = 0, 1024, 8192),  -- 1kB for SRPv3, 8KB for AXI stream
            APP_STREAMS_G      => RSSI_SIZE_C,
            CLK_FREQUENCY_G    => CLK_FREQUENCY_C,
            WINDOW_ADDR_SIZE_G => ite(i = 0, 4, 5),  -- 2^4 buffers for SRPv3, 2^5 buffers for AXI stream
            MAX_RETRANS_CNT_G  => 16,
            APP_AXIS_CONFIG_G  => AXIS_CONFIG_C,
            TSP_AXIS_CONFIG_G  => EMAC_AXIS_CONFIG_C)
         port map (
            clk_i                => ethClk,
            rst_i                => ethRst,
            openRq_i             => '1',
            rssiConnected_o      => rssiLinkUp(i),
            -- Application Layer Interface
            sAppAxisMasters_i(0) => rssiIbMasters(i),
            sAppAxisSlaves_o(0)  => rssiIbSlaves(i),
            mAppAxisMasters_o(0) => rssiObMasters(i),
            mAppAxisSlaves_i(0)  => rssiObSlaves(i),
            -- Transport Layer Interface
            sTspAxisMaster_i     => obServerMasters(i),
            sTspAxisSlave_o      => obServerSlaves(i),
            mTspAxisMaster_o     => ibServerMasters(i),
            mTspAxisSlave_i      => ibServerSlaves(i),
            -- AXI-Lite Interface
            axiClk_i             => ethClk,
            axiRst_i             => ethRst,
            axilReadMaster       => axilReadMasters(RSSI_INDEX_C+i),
            axilReadSlave        => axilReadSlaves(RSSI_INDEX_C+i),
            axilWriteMaster      => axilWriteMasters(RSSI_INDEX_C+i),
            axilWriteSlave       => axilWriteSlaves(RSSI_INDEX_C+i));

   end generate GEN_VEC;

   ------------------------------------------------------------------
   -- RSSI[0] @ UDP Port(SERVER_PORTS_C[0]) = Register access control
   ------------------------------------------------------------------
   U_SRPv3 : entity surf.SrpV3AxiLite
      generic map (
         TPD_G               => TPD_G,
         SLAVE_READY_EN_G    => true,
         GEN_SYNC_FIFO_G     => true,
         AXI_STREAM_CONFIG_G => RSSI_AXIS_CONFIG_C)
      port map (
         -- Streaming Slave (Rx) Interface (sAxisClk domain)
         sAxisClk         => ethClk,
         sAxisRst         => ethRst,
         sAxisMaster      => rssiObMasters(0),
         sAxisSlave       => rssiObSlaves(0),
         -- Streaming Master (Tx) Data Interface (mAxisClk domain)
         mAxisClk         => ethClk,
         mAxisRst         => ethRst,
         mAxisMaster      => rssiIbMasters(0),
         mAxisSlave       => rssiIbSlaves(0),
         -- Master AXI-Lite Interface (axilClk domain)
         axilClk          => ethClk,
         axilRst          => ethRst,
         mAxilReadMaster  => mAxilReadMaster,
         mAxilReadSlave   => mAxilReadSlave,
         mAxilWriteMaster => mAxilWriteMaster,
         mAxilWriteSlave  => mAxilWriteSlave);

   ---------------------------------------------------------------
   -- RSSI[1] @ UDP Port(SERVER_PORTS_C[1]) = AXI Stream Interface
   ---------------------------------------------------------------
   rssiIbMasters(1) <= ibRudpMaster;
   ibRudpSlave      <= rssiIbSlaves(1);
   obRudpMaster     <= rssiObMasters(1);
   rssiObSlaves(1)  <= obRudpSlave;

   ------------------------
   -- AXI Stream Monitoring
   ------------------------
   U_AXIS_MON : entity surf.AxiStreamMonAxiL
      generic map(
         TPD_G            => TPD_G,
         COMMON_CLK_G     => true,
         AXIS_CLK_FREQ_G  => CLK_FREQUENCY_C,
         AXIS_NUM_SLOTS_G => 2,
         AXIS_CONFIG_G    => RSSI_AXIS_CONFIG_C)
      port map(
         -- AXIS Stream Interface
         axisClk          => ethClk,
         axisRst          => ethRst,
         axisMasters(0)   => rssiIbMasters(1),
         axisMasters(1)   => rssiObMasters(1),
         axisSlaves(0)    => rssiIbSlaves(1),
         axisSlaves(1)    => rssiObSlaves(1),
         -- AXI lite slave port for register access
         axilClk          => ethClk,
         axilRst          => ethRst,
         sAxilWriteMaster => axilWriteMasters(AXIS_MON_INDEX_C),
         sAxilWriteSlave  => axilWriteSlaves(AXIS_MON_INDEX_C),
         sAxilReadMaster  => axilReadMasters(AXIS_MON_INDEX_C),
         sAxilReadSlave   => axilReadSlaves(AXIS_MON_INDEX_C));

end mapping;
