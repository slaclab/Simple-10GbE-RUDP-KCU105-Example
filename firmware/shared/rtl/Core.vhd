-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Core Firmware Module
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
use surf.RssiPkg.all;
use surf.I2cPkg.all;
use surf.I2cMuxPkg.all;

library work;
use work.CorePkg.all;

library unisim;
use unisim.vcomponents.all;

entity Core is
   generic (
      TPD_G        : time := 1 ns;
      BUILD_INFO_G : BuildInfoType;
      SIMULATION_G : boolean;
      ETH_BUILD_G  : BuildEthType;
      IP_ADDR_G    : slv(31 downto 0);
      DHCP_G       : boolean);
   port (
      -- Clock and Reset
      axilClk         : out   sl;
      axilRst         : out   sl;
      -- AXI-Stream Interface
      ibRudpMaster    : in    AxiStreamMasterType;
      ibRudpSlave     : out   AxiStreamSlaveType;
      obRudpMaster    : out   AxiStreamMasterType;
      obRudpSlave     : in    AxiStreamSlaveType;
      -- AXI-Lite Interface
      axilReadMaster  : out   AxiLiteReadMasterType;
      axilReadSlave   : in    AxiLiteReadSlaveType;
      axilWriteMaster : out   AxiLiteWriteMasterType;
      axilWriteSlave  : in    AxiLiteWriteSlaveType;
      -- I2C Ports
      sfpTxDisL       : out   sl;
      i2cRstL         : out   sl;
      i2cScl          : inout sl;
      i2cSda          : inout sl;
      -- SYSMON Ports
      vPIn            : in    sl;
      vNIn            : in    sl;
      -- System Ports
      extRst          : in    sl;
      sysClk300P      : in    sl;
      sysClk300N      : in    sl;
      emcClk          : in    sl;
      heartbeat       : out   sl;
      phyReady        : out   sl;
      rssiLinkUp      : out   slv(1 downto 0);
      -- Boot Memory Ports
      flashCsL        : out   sl;
      flashMosi       : out   sl;
      flashMiso       : in    sl;
      flashHoldL      : out   sl;
      flashWp         : out   sl;
      -- SFP ETH Ports
      ethClkP         : in    sl;
      ethClkN         : in    sl;
      ethRxP          : in    sl;
      ethRxN          : in    sl;
      ethTxP          : out   sl;
      ethTxN          : out   sl;
      -- RJ45 ETH Ports
      phyClkP         : in    sl;
      phyClkN         : in    sl;
      phyRxP          : in    sl;
      phyRxN          : in    sl;
      phyTxP          : out   sl;
      phyTxN          : out   sl;
      phyMdc          : out   sl;
      phyMdio         : inout sl;
      phyRstN         : out   sl;
      phyIrqN         : in    sl);
end Core;

architecture mapping of Core is

   constant AXIL_CLK_FREQ_C : real := ite((ETH_BUILD_G = SFP_10G_C), 156.25E+6, 125.0E+6);

   constant VERSION_INDEX_C : natural := 0;
   constant SYS_MON_INDEX_C : natural := 1;
   constant PROM_INDEX_C    : natural := 2;  -- 2:3
   constant ETH_INDEX_C     : natural := 4;
   constant I2C_INDEX_C     : natural := 5;
   constant APP_INDEX_C     : natural := 6;

   constant NUM_AXIL_MASTERS_C : positive := 7;

   constant XBAR_CONFIG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := (
      VERSION_INDEX_C => (baseAddr => x"0000_0000", addrBits => 16, connectivity => x"FFFF"),
      SYS_MON_INDEX_C => (baseAddr => x"0001_0000", addrBits => 16, connectivity => x"FFFF"),
      PROM_INDEX_C+0  => (baseAddr => x"0002_0000", addrBits => 16, connectivity => x"FFFF"),
      PROM_INDEX_C+1  => (baseAddr => x"0003_0000", addrBits => 16, connectivity => x"FFFF"),
      ETH_INDEX_C     => (baseAddr => x"0010_0000", addrBits => 20, connectivity => x"FFFF"),
      I2C_INDEX_C     => (baseAddr => x"0020_0000", addrBits => 20, connectivity => x"FFFF"),
      APP_INDEX_C     => (baseAddr => x"8000_0000", addrBits => 31, connectivity => x"FFFF"));

   signal mAxilWriteMaster : AxiLiteWriteMasterType;
   signal mAxilWriteSlave  : AxiLiteWriteSlaveType;
   signal mAxilReadMaster  : AxiLiteReadMasterType;
   signal mAxilReadSlave   : AxiLiteReadSlaveType;

   signal axilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal axilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0) := (others => AXI_LITE_WRITE_SLAVE_EMPTY_SLVERR_C);
   signal axilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal axilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0)  := (others => AXI_LITE_READ_SLAVE_EMPTY_SLVERR_C);

   constant XBAR_I2C_CONFIG_C : AxiLiteCrossbarMasterConfigArray(7 downto 0) := genAxiLiteConfig(8, XBAR_CONFIG_C(I2C_INDEX_C).baseAddr, 16, 12);

   constant SFF8472_I2C_CONFIG_C : I2cAxiLiteDevArray(1 downto 0) := (
      0              => MakeI2cAxiLiteDevType(
         i2cAddress  => "1010000",      -- 2 wire address 1010000X (A0h)
         dataSize    => 8,              -- in units of bits
         addrSize    => 8,              -- in units of bits
         endianness  => '0',            -- Little endian
         repeatStart => '1'),           -- No repeat start
      1              => MakeI2cAxiLiteDevType(
         i2cAddress  => "1010001",      -- 2 wire address 1010001X (A2h)
         dataSize    => 8,              -- in units of bits
         addrSize    => 8,              -- in units of bits
         endianness  => '0',            -- Little endian
         repeatStart => '1'));          -- Repeat Start

   signal i2cReadMasters  : AxiLiteReadMasterArray(7 downto 0);
   signal i2cReadSlaves   : AxiLiteReadSlaveArray(7 downto 0)  := (others => AXI_LITE_READ_SLAVE_EMPTY_DECERR_C);
   signal i2cWriteMasters : AxiLiteWriteMasterArray(7 downto 0);
   signal i2cWriteSlaves  : AxiLiteWriteSlaveArray(7 downto 0) := (others => AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C);

   signal i2ci : i2c_in_type;
   signal i2coVec : i2c_out_array(8 downto 0) := (
      others    => (
         scl    => '1',
         scloen => '1',
         sda    => '1',
         sdaoen => '1',
         enable => '0'));
   signal i2co : i2c_out_type;

   signal bootCsL  : slv(1 downto 0);
   signal bootSck  : slv(1 downto 0);
   signal bootMosi : slv(1 downto 0);
   signal bootMiso : slv(1 downto 0);
   signal di       : slv(3 downto 0);
   signal do       : slv(3 downto 0);
   signal sck      : sl;

   signal eos      : sl;
   signal userCclk : sl;

   signal spiBusyIn  : slv(1 downto 0);
   signal spiBusyOut : slv(1 downto 0);

   signal clk : sl;
   signal rst : sl;

begin

   axilClk <= clk;
   axilRst <= rst;

   sfpTxDisL <= '1';
   i2cRstL   <= not(rst);

   U_Heartbeat : entity surf.Heartbeat
      generic map (
         TPD_G        => TPD_G,
         PERIOD_IN_G  => 6.4E-9,        --units of seconds
         PERIOD_OUT_G => 1.0E-0)        --units of seconds
      port map (
         clk => clk,
         rst => rst,
         o   => Heartbeat);

   GEN_ETH : if (SIMULATION_G = false) generate

      U_Rudp : entity work.Rudp
         generic map (
            TPD_G            => TPD_G,
            ETH_BUILD_G      => ETH_BUILD_G,
            IP_ADDR_G        => IP_ADDR_G,
            DHCP_G           => DHCP_G,
            AXIL_BASE_ADDR_G => XBAR_CONFIG_C(ETH_INDEX_C).baseAddr)
         port map (
            -- System Ports
            extRst           => extRst,
            sysClk300P       => sysClk300P,
            sysClk300N       => sysClk300N,
            -- Ethernet Status
            phyReady         => phyReady,
            rssiLinkUp       => rssiLinkUp,
            -- Clock and Reset
            axilClk          => clk,
            axilRst          => rst,
            -- AXI-Stream Interface
            ibRudpMaster     => ibRudpMaster,
            ibRudpSlave      => ibRudpSlave,
            obRudpMaster     => obRudpMaster,
            obRudpSlave      => obRudpSlave,
            -- Master AXI-Lite Interface
            mAxilReadMaster  => mAxilReadMaster,
            mAxilReadSlave   => mAxilReadSlave,
            mAxilWriteMaster => mAxilWriteMaster,
            mAxilWriteSlave  => mAxilWriteSlave,
            -- Slave AXI-Lite Interfaces
            sAxilReadMaster  => axilReadMasters(ETH_INDEX_C),
            sAxilReadSlave   => axilReadSlaves(ETH_INDEX_C),
            sAxilWriteMaster => axilWriteMasters(ETH_INDEX_C),
            sAxilWriteSlave  => axilWriteSlaves(ETH_INDEX_C),
            -- SFP ETH Ports
            ethClkP          => ethClkP,
            ethClkN          => ethClkN,
            ethRxP           => ethRxP,
            ethRxN           => ethRxN,
            ethTxP           => ethTxP,
            ethTxN           => ethTxN,
            -- RJ45 ETH Ports
            phyClkP          => phyClkP,
            phyClkN          => phyClkN,
            phyRxP           => phyRxP,
            phyRxN           => phyRxN,
            phyTxP           => phyTxP,
            phyTxN           => phyTxN,
            phyMdc           => phyMdc,
            phyMdio          => phyMdio,
            phyRstN          => phyRstN,
            phyIrqN          => phyIrqN);

   end generate;

   GEN_ROGUE_TCP : if (SIMULATION_G = true) generate

      U_ClkRst : entity surf.ClkRst
         generic map (
            CLK_PERIOD_G      => 6.4 ns,
            RST_START_DELAY_G => 0 ns,
            RST_HOLD_TIME_G   => 1 us)
         port map (
            clkP => clk,
            rst  => rst);

      U_TcpToAxiLite : entity surf.RogueTcpMemoryWrap
         generic map (
            TPD_G      => TPD_G,
            PORT_NUM_G => 10000)        -- TCP Ports [10000,10001]
         port map (
            axilClk         => clk,
            axilRst         => rst,
            axilReadMaster  => mAxilReadMaster,
            axilReadSlave   => mAxilReadSlave,
            axilWriteMaster => mAxilWriteMaster,
            axilWriteSlave  => mAxilWriteSlave);

      U_TcpToAxiStream : entity surf.RogueTcpStreamWrap
         generic map (
            TPD_G         => TPD_G,
            PORT_NUM_G    => 10002,     -- TCP Ports [10002,10003]
            SSI_EN_G      => true,
            AXIS_CONFIG_G => RSSI_AXIS_CONFIG_C)
         port map (
            axisClk     => clk,
            axisRst     => rst,
            sAxisMaster => ibRudpMaster,
            sAxisSlave  => ibRudpSlave,
            mAxisMaster => obRudpMaster,
            mAxisSlave  => obRudpSlave);

   end generate;

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
         sAxiWriteMasters(0) => mAxilWriteMaster,
         sAxiWriteSlaves(0)  => mAxilWriteSlave,
         sAxiReadMasters(0)  => mAxilReadMaster,
         sAxiReadSlaves(0)   => mAxilReadSlave,
         mAxiWriteMasters    => axilWriteMasters,
         mAxiWriteSlaves     => axilWriteSlaves,
         mAxiReadMasters     => axilReadMasters,
         mAxiReadSlaves      => axilReadSlaves,
         axiClk              => clk,
         axiClkRst           => rst);

   ---------------------------
   -- AXI-Lite: Version Module
   ---------------------------
   U_AxiVersion : entity surf.AxiVersion
      generic map (
         TPD_G           => TPD_G,
         BUILD_INFO_G    => BUILD_INFO_G,
         CLK_PERIOD_G    => (1.0/AXIL_CLK_FREQ_C),
         XIL_DEVICE_G    => "ULTRASCALE",
         USE_SLOWCLK_G   => true,
         EN_DEVICE_DNA_G => true,
         EN_ICAP_G       => true)
      port map (
         slowClk        => clk,
         axiReadMaster  => axilReadMasters(VERSION_INDEX_C),
         axiReadSlave   => axilReadSlaves(VERSION_INDEX_C),
         axiWriteMaster => axilWriteMasters(VERSION_INDEX_C),
         axiWriteSlave  => axilWriteSlaves(VERSION_INDEX_C),
         axiClk         => clk,
         axiRst         => rst);

   GEN_REAL : if (SIMULATION_G = false) generate

      -----------------------------
      -- AXI-Lite: Boot PROM Module
      -----------------------------
      GEN_VEC : for i in 1 downto 0 generate

         U_BootProm : entity surf.AxiMicronN25QCore
            generic map (
               TPD_G          => TPD_G,
               AXI_CLK_FREQ_G => AXIL_CLK_FREQ_C,         -- units of Hz
               SPI_CLK_FREQ_G => (AXIL_CLK_FREQ_C/16.0))  -- units of Hz
            port map (
               -- FLASH Memory Ports
               csL            => bootCsL(i),
               sck            => bootSck(i),
               mosi           => bootMosi(i),
               miso           => bootMiso(i),
               -- Shared SPI Interface
               busyIn         => spiBusyIn(i),
               busyOut        => spiBusyOut(i),
               -- AXI-Lite Register Interface
               axiReadMaster  => axilReadMasters(PROM_INDEX_C+i),
               axiReadSlave   => axilReadSlaves(PROM_INDEX_C+i),
               axiWriteMaster => axilWriteMasters(PROM_INDEX_C+i),
               axiWriteSlave  => axilWriteSlaves(PROM_INDEX_C+i),
               -- Clocks and Resets
               axiClk         => clk,
               axiRst         => rst);

      end generate GEN_VEC;

      flashCsL    <= bootCsL(1);
      flashMosi   <= bootMosi(1);
      bootMiso(1) <= flashMiso;
      flashHoldL  <= '1';
      flashWp     <= '1';

      U_STARTUPE3 : STARTUPE3
         generic map (
            PROG_USR      => "FALSE",  -- Activate program event security feature. Requires encrypted bitstreams.
            SIM_CCLK_FREQ => 0.0)  -- Set the Configuration Clock Frequency(ns) for simulation
         port map (
            CFGCLK    => open,  -- 1-bit output: Configuration main clock output
            CFGMCLK   => open,  -- 1-bit output: Configuration internal oscillator clock output
            DI        => di,  -- 4-bit output: Allow receiving on the D[3:0] input pins
            EOS       => eos,  -- 1-bit output: Active high output signal indicating the End Of Startup.
            PREQ      => open,  -- 1-bit output: PROGRAM request to fabric output
            DO        => do,  -- 4-bit input: Allows control of the D[3:0] pin outputs
            DTS       => "1110",  -- 4-bit input: Allows tristate of the D[3:0] pins
            FCSBO     => bootCsL(0),  -- 1-bit input: Contols the FCS_B pin for flash access
            FCSBTS    => '0',           -- 1-bit input: Tristate the FCS_B pin
            GSR       => '0',  -- 1-bit input: Global Set/Reset input (GSR cannot be used for the port name)
            GTS       => '0',  -- 1-bit input: Global 3-state input (GTS cannot be used for the port name)
            KEYCLEARB => '0',  -- 1-bit input: Clear AES Decrypter Key input from Battery-Backed RAM (BBRAM)
            PACK      => '0',  -- 1-bit input: PROGRAM acknowledge input
            USRCCLKO  => userCclk,      -- 1-bit input: User CCLK input
            USRCCLKTS => '0',  -- 1-bit input: User CCLK 3-state enable input
            USRDONEO  => '1',  -- 1-bit input: User DONE pin output control
            USRDONETS => '0');  -- 1-bit input: User DONE 3-state enable output

      do          <= "111" & bootMosi(0);
      bootMiso(0) <= di(1);
      sck         <= uOr(bootSck);

      userCclk <= emcClk when(eos = '0') else sck;

      spiBusyIn(0) <= spiBusyOut(1);
      spiBusyIn(1) <= spiBusyOut(0);

      --------------------------
      -- AXI-Lite: SYSMON Module
      --------------------------
      U_SysMon : entity work.Sysmon
         generic map (
            TPD_G => TPD_G)
         port map (
            axiReadMaster  => axilReadMasters(SYS_MON_INDEX_C),
            axiReadSlave   => axilReadSlaves(SYS_MON_INDEX_C),
            axiWriteMaster => axilWriteMasters(SYS_MON_INDEX_C),
            axiWriteSlave  => axilWriteSlaves(SYS_MON_INDEX_C),
            axiClk         => clk,
            axiRst         => rst,
            vPIn           => vPIn,
            vNIn           => vNIn);

      -----------------------------------------
      -- TCA9548APWR I2C MUX + AxiLite Crossbar
      -----------------------------------------
      U_XbarI2cMux : entity surf.AxiLiteCrossbarI2cMux
         generic map (
            TPD_G              => TPD_G,
            -- I2C MUX Generics
            MUX_DECODE_MAP_G   => I2C_MUX_DECODE_MAP_TCA9548_C,
            I2C_MUX_ADDR_G     => b"1110_100",
            I2C_SCL_FREQ_G     => 400.0E+3,  -- units of Hz
            AXIL_CLK_FREQ_G    => AXIL_CLK_FREQ_C,
            -- AXI-Lite Crossbar Generics
            NUM_MASTER_SLOTS_G => 8,
            MASTERS_CONFIG_G   => XBAR_I2C_CONFIG_C)
         port map (
            -- Clocks and Resets
            axilClk           => clk,
            axilRst           => rst,
            -- Slave AXI-Lite Interface
            sAxilWriteMaster  => axilWriteMasters(I2C_INDEX_C),
            sAxilWriteSlave   => axilWriteSlaves(I2C_INDEX_C),
            sAxilReadMaster   => axilReadMasters(I2C_INDEX_C),
            sAxilReadSlave    => axilReadSlaves(I2C_INDEX_C),
            -- Master AXI-Lite Interfaces
            mAxilWriteMasters => i2cWriteMasters,
            mAxilWriteSlaves  => i2cWriteSlaves,
            mAxilReadMasters  => i2cReadMasters,
            mAxilReadSlaves   => i2cReadSlaves,
            -- I2C MUX Ports
            i2ci              => i2ci,
            i2co              => i2coVec(8));

      GEN_SFP :
      for i in 2 to 3 generate
         U_I2C : entity surf.AxiI2cRegMasterCore
            generic map (
               TPD_G          => TPD_G,
               I2C_SCL_FREQ_G => 400.0E+3,  -- units of Hz
               DEVICE_MAP_G   => SFF8472_I2C_CONFIG_C,
               AXI_CLK_FREQ_G => AXIL_CLK_FREQ_C)
            port map (
               -- I2C Ports
               i2ci           => i2ci,
               i2co           => i2coVec(i),
               -- AXI-Lite Register Interface
               axiReadMaster  => i2cReadMasters(i),
               axiReadSlave   => i2cReadSlaves(i),
               axiWriteMaster => i2cWriteMasters(i),
               axiWriteSlave  => i2cWriteSlaves(i),
               -- Clocks and Resets
               axiClk         => clk,
               axiRst         => rst);
      end generate GEN_SFP;

      process(i2cReadMasters, i2cWriteMasters, i2coVec)
         variable tmp : i2c_out_type;
      begin
         -- Init (Default to I2C MUX endpoint)
         tmp := i2coVec(8);
         -- Check for TXN after XBAR/I2C_MUX
         for i in 0 to 7 loop
            if (i2cWriteMasters(i).awvalid = '1') or (i2cReadMasters(i).arvalid = '1') then
               tmp := i2coVec(i);
            end if;
         end loop;
         -- Return result
         i2co <= tmp;
      end process;

      IOBUF_SCL : IOBUF
         port map (
            O  => i2ci.scl,
            IO => i2cScl,
            I  => i2co.scl,
            T  => i2co.scloen);

      IOBUF_SDA : IOBUF
         port map (
            O  => i2ci.sda,
            IO => i2cSda,
            I  => i2co.sda,
            T  => i2co.sdaoen);

   end generate;

   -----------------------------------
   -- Map the Application AXI-Lite Bus
   -----------------------------------
   axilReadMaster               <= axilReadMasters(APP_INDEX_C);
   axilReadSlaves(APP_INDEX_C)  <= axilReadSlave;
   axilWriteMaster              <= axilWriteMasters(APP_INDEX_C);
   axilWriteSlaves(APP_INDEX_C) <= axilWriteSlave;

end mapping;
