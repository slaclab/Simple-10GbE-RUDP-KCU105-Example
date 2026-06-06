-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: RoCEv2 dispatcher of work requests to the RoCEv2 engine
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
use ieee.std_logic_unsigned.all;
use ieee.std_logic_arith.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.AxiLitePkg.all;
use surf.RoCEv2Pkg.all;

entity WorkReqDispatcher is
   generic (
      TPD_G                   : time                  := 1 ns;
      RST_ASYNC_G             : boolean               := false;
      DISPATCH_COUNTER_BITS_G : natural range 0 to 31 := 24);
   port (
      roceClk          : in  std_logic;
      roceRst          : in  std_logic;
      -- Roce Work Req
      workReqMaster    : out RoceWorkReqMasterType;
      workReqSlave     : in  RoceWorkReqSlaveType;
      -- Starting flag
      startingDispatch : out sl;
      -- Axi-Lite Registers
      axilReadMaster   : in  AxiLiteReadMasterType  := AXI_LITE_READ_MASTER_INIT_C;
      axilReadSlave    : out AxiLiteReadSlaveType;
      axilWriteMaster  : in  AxiLiteWriteMasterType := AXI_LITE_WRITE_MASTER_INIT_C;
      axilWriteSlave   : out AxiLiteWriteSlaveType);
end entity WorkReqDispatcher;

architecture rtl of WorkReqDispatcher is

   type AxilRegType is record
      startDispatching : sl;
      dispatchCounter  : slv(DISPATCH_COUNTER_BITS_G-1 downto 0);
      len              : slv(31 downto 0);
      rKey             : slv(31 downto 0);
      lKey             : slv(31 downto 0);
      sQpn             : slv(23 downto 0);
      dQpn             : slv(24 downto 0);
      rAddr            : slv(63 downto 0);
      addrWrapCount    : slv(31 downto 0);
      axilReadSlave    : AxiLiteReadSlaveType;
      axilWriteSlave   : AxiLiteWriteSlaveType;
   end record AxilRegType;

   constant AXIL_REG_INIT_C : AxilRegType := (
      startDispatching => '0',
      dispatchCounter  => (others => '0'),
      len              => (others => '0'),
      rKey             => (others => '0'),
      lKey             => (others => '0'),
      sQpn             => (others => '0'),
      dQpn             => (others => '0'),
      rAddr            => (others => '0'),
      addrWrapCount    => (others => '0'),
      axilReadSlave    => AXI_LITE_READ_SLAVE_INIT_C,
      axilWriteSlave   => AXI_LITE_WRITE_SLAVE_INIT_C
      );

   signal regR   : AxilRegType := AXIL_REG_INIT_C;
   signal regRin : AxilRegType;

   -- Track previous rAddr to detect when startZmq restarts with a new MR.
   -- Initialised to all-ones so the very first write always triggers a reset.
   signal prevRAddr : slv(63 downto 0) := (others => '1');

   type DispStateType is (st0_idle, st1_sending);

   type DispRegType is record
      state     : DispStateType;
      count     : slv(DISPATCH_COUNTER_BITS_G-1 downto 0);
      addrCount : slv(DISPATCH_COUNTER_BITS_G-1 downto 0);
      txMaster  : RoceWorkReqMasterType;
   end record DispRegType;

   constant DISP_REG_INIT_C : DispRegType := (
      state     => st0_idle,
      count     => (others => '0'),
      addrCount => (others => '0'),
      txMaster  => ROCE_WORK_REQ_MASTER_INIT_C
      );

   signal dispR   : DispRegType := DISP_REG_INIT_C;
   signal dispRin : DispRegType;

   signal startDispatching : sl;

begin  -- architecture rtl

   -----------------------------------------------------------------------------
   -- Axi-Lite Regs
   -----------------------------------------------------------------------------
   regComb : process (axilReadMaster, axilWriteMaster, regR) is
      variable v      : AxilRegType;
      variable regCon : AxiLiteEndPointType;
   begin

      v := regR;

      axiSlaveWaitTxn(regCon, axilWriteMaster, axilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      axiSlaveRegister (regCon, x"F00", 0, v.startDispatching);
      axiSlaveRegister (regCon, x"F00", 1, v.dispatchCounter);
      axiSlaveRegister (regCon, x"F04", 0, v.len);
      axiSlaveRegister (regCon, x"F08", 0, v.rKey);
      axiSlaveRegister (regCon, x"F0C", 0, v.lKey);
      axiSlaveRegister (regCon, x"F10", 0, v.sQpn);
      axiSlaveRegister (regCon, x"F14", 0, v.dQpn);
      axiSlaveRegister (regCon, x"F18", 0, v.rAddr);
      axiSlaveRegister (regCon, x"F20", 0, v.addrWrapCount);

      axiSlaveDefault(regCon, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      axilWriteSlave <= regR.axilWriteSlave;
      axilReadSlave  <= regR.axilReadSlave;

      regRin <= v;

   end process regComb;

   regSeq : process (RoceClk, RoceRst) is
   begin
      if (RST_ASYNC_G) and (RoceRst = '1') then
         regR      <= AXIL_REG_INIT_C after TPD_G;
         prevRAddr <= (others => '1') after TPD_G;
      elsif (rising_edge(RoceClk)) then
         if (RST_ASYNC_G = false) and (RoceRst = '1') then
            regR      <= AXIL_REG_INIT_C after TPD_G;
            prevRAddr <= (others => '1') after TPD_G;
         else
            regR      <= regRin     after TPD_G;
            -- Track previous value of rAddr to detect changes in dispComb
            prevRAddr <= regR.rAddr after TPD_G;
         end if;
      end if;
   end process regSeq;

   SynchronizerEdge_1 : entity surf.SynchronizerEdge
      generic map (
         TPD_G         => TPD_G,
         BYPASS_SYNC_G => true
         )
      port map (
         clk        => RoceClk,
         dataIn     => regR.startDispatching,
         risingEdge => startDispatching
         );

   startingDispatch <= startDispatching;

   -----------------------------------------------------------------------------
   -- Dispatcher
   -----------------------------------------------------------------------------
   dispComb : process (dispR, prevRAddr, regR, startDispatching, workReqSlave) is
      variable v         : dispRegType;
      variable idPadding : slv(63 downto DISPATCH_COUNTER_BITS_G) := (others => '0');
      variable nextAddr  : slv(DISPATCH_COUNTER_BITS_G-1 downto 0);
   begin

      v := dispR;

      if workReqSlave.ready = '1' then
         v.txMaster.valid := '0';
      end if;

      case dispR.state is
         -------------------------------------------------------------------------
         when st0_idle =>
            -- Reset addrCount when rAddr changes (new MR after startZmq restart).
            -- addrCount persists across multiple dispatch bursts within a session.
            if regR.rAddr /= prevRAddr then
               v.addrCount := (others => '0');
            end if;
            if startDispatching = '1' then
               v.state := st1_sending;
            end if;
         -----------------------------------------------------------------------
         when st1_sending =>
            if v.txMaster.valid = '0' then
               v.txMaster.id        := idPadding & dispR.count + 1;
               v.txMaster.opCode    := x"1";
               v.txMaster.flags     := "00010";  -- RDMA Write with Immediate
               v.txMaster.rAddr     := regR.rAddr + (dispR.addrCount * regR.len);
               v.txMaster.rKey      := regR.rKey;
               v.txMaster.len       := regR.len;
               v.txMaster.lAddr     := (others => '0');
               v.txMaster.lKey      := regR.lKey;
               v.txMaster.sQpn      := regR.sQpn;
               v.txMaster.solicited := '0';
               v.txMaster.comp      := (others => '0');
               v.txMaster.swap      := (others => '0');
               -- Set immediate data channel ID to 1 so the rogue StreamWriter routes
               -- incoming RDMA frames to channel 1 (dataWriter.getChannel(1)).
               -- Bits [7:0] of immDt are decoded by Server.cpp as the rogue stream
               -- channel; channel 0 is reserved for the UDP/RSSI stream.
               v.txMaster.immDt     := conv_std_logic_vector(1, v.txMaster.immDt'length);
               v.txMaster.rKeyToInv := (others => '0');
               v.txMaster.srqn      := (others => '0');
               v.txMaster.dQpn      := (others => '0');
               v.txMaster.qKey      := (others => '0');
               v.txMaster.valid     := '1';

               -- Advance addrCount, wrapping at addrWrapCount
               nextAddr := dispR.addrCount + 1;
               if nextAddr >= regR.addrWrapCount then
                  v.addrCount := (others => '0');
               else
                  v.addrCount := nextAddr;
               end if;

               -- Advance dispatch counter
               if dispR.count < regR.dispatchCounter - 1 then
                  v.count := v.count + 1;
                  v.state := st1_sending;
               else
                  v.count := (others => '0');
                  v.state := st0_idle;
               end if;
            end if;
         -----------------------------------------------------------------------
         when others =>
            v := DISP_REG_INIT_C;
      end case;

      workReqMaster <= dispR.txMaster;
      dispRin       <= v;

   end process dispComb;

   dispSeq : process (RoceClk, RoceRst) is
   begin
      if (RST_ASYNC_G) and (RoceRst = '1') then
         dispR <= DISP_REG_INIT_C after TPD_G;
      elsif (rising_edge(RoceClk)) then
         if (RST_ASYNC_G = false) and (RoceRst = '1') then
            dispR <= DISP_REG_INIT_C after TPD_G;
         else
            dispR <= dispRin after TPD_G;
         end if;
      end if;
   end process dispSeq;

end architecture rtl;
