-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Consolidated RoCEv2 AXI-Stream RDMA payload module.
--
--   Replaces the three-module split (WorkReqDispatcher + DmaTestPatternServer +
--   WorkCompChecker) with ONE module that owns the RoCEv2 host interface:
--     * REPACK      : drain an inbound AXI-Stream (PRBS) payload into the surf
--                     290-bit RoceDmaReadResp record, one tLast-packet per
--                     DMA-read request.
--     * DISPATCH    : issue RDMA-WRITE-with-immediate work requests.
--     * COMPLETION  : count success/unsuccess work completions.
--     * REG FILE    : ONE merged AXI-Lite slave exposing the union register map.
-------------------------------------------------------------------------------
-- This file is part of 'Simple-10GbE-RUDP-KCU105-Example'.
-- It is subject to the license terms in the LICENSE.txt file found in the
-- top-level directory of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of 'Simple-10GbE-RUDP-KCU105-Example', including this file,
-- may be copied, modified, propagated, or distributed except according to
-- the terms contained in the LICENSE.txt file.
-------------------------------------------------------------------------------

-- numeric_std ONLY: do NOT add ieee.std_logic_unsigned or ieee.std_logic_arith.
-- All arithmetic uses explicit numeric_std unsigned()/to_unsigned() conversions.
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.SsiPkg.all;
use surf.AxiLitePkg.all;
use surf.RoCEv2Pkg.all;

entity RoCEv2AxiStreamRdma is
   generic (
      TPD_G                   : time                   := 1 ns;
      RST_ASYNC_G             : boolean                := false;
      -- Inbound payload stream config (FIFO slave side). The internal FIFO
      -- converts it to the 32-byte RoCEv2 width; passing a narrower / TKEEP_COMP_C
      -- config (e.g. RSSI_AXIS_CONFIG_C) exercises the tKeep/byteEn repack path.
      AXIS_CONFIG_G           : AxiStreamConfigType    := ssiAxiStreamConfig(dataBytes => TDATA_ROCE_NUM_BYTES_C, tKeepMode => TKEEP_NORMAL_C, tDestBits => 0);
      -- Repack FIFO depth: >= 2 packets for len<=8191.
      FIFO_ADDR_WIDTH_G       : integer range 4 to 48  := 9;
      DISPATCH_COUNTER_BITS_G : positive               := 24);
   port (
      roceClk           : in  sl;
      roceRst           : in  sl;
      -- Inbound AXI-Stream payload (the PRBS stream from App, wired in Phase 2)
      sAxisMaster       : in  AxiStreamMasterType;
      sAxisSlave        : out AxiStreamSlaveType;
      -- RoCEv2 DMA read request / response (surf RoCEv2Engine interface)
      dmaReadReqMaster  : in  RoceDmaReadReqMasterType;
      dmaReadReqSlave   : out RoceDmaReadReqSlaveType;
      dmaReadRespMaster : out RoceDmaReadRespMasterType;
      dmaReadRespSlave  : in  RoceDmaReadRespSlaveType;
      -- RoCEv2 work request (dispatch out)
      workReqMaster     : out RoceWorkReqMasterType;
      workReqSlave      : in  RoceWorkReqSlaveType;
      -- RoCEv2 work completion (completion in)
      workCompMaster    : in  RoceWorkCompMasterType;
      workCompSlave     : out RoceWorkCompSlaveType;
      -- AXI-Lite slave (single merged register file)
      axilReadMaster    : in  AxiLiteReadMasterType  := AXI_LITE_READ_MASTER_INIT_C;
      axilReadSlave     : out AxiLiteReadSlaveType;
      axilWriteMaster   : in  AxiLiteWriteMasterType := AXI_LITE_WRITE_MASTER_INIT_C;
      axilWriteSlave    : out AxiLiteWriteSlaveType);
end entity RoCEv2AxiStreamRdma;

architecture rtl of RoCEv2AxiStreamRdma is

   -- Internal 32-byte RoCEv2 SSI config (FIFO master / REPACK drain side). The
   -- FIFO converts AXIS_CONFIG_G to this width; the REPACK FSM maps tKeep(31:0)
   -- directly into the 290-bit byteEnable field.
   constant AXIS_CONFIG_C : AxiStreamConfigType :=
      ssiAxiStreamConfig(
         dataBytes => TDATA_ROCE_NUM_BYTES_C,
         tKeepMode => TKEEP_NORMAL_C,
         tDestBits => 0);

   ----------------------------------------------------------------------------
   -- ONE merged register record: dispatcher + checker control fields plus the
   -- AXI-Lite slave outputs. successCounter/unsuccessCounter are driven by the
   -- completion FSM, so the RO exposure at 0x100/0x104 reads the same record
   -- (single driver).
   ----------------------------------------------------------------------------
   -- Completion-counter FSM state (Block D).
   type CompStateType is (ST0_IDLE, ST1_RECEIVED);

   type RegType is record
      -- Dispatch control (from old WorkReqDispatcher AxilRegType)
      startDispatching : sl;
      len              : slv(31 downto 0);
      rKey             : slv(31 downto 0);
      lKey             : slv(31 downto 0);
      sQpn             : slv(23 downto 0);
      dQpn             : slv(24 downto 0);
      rAddr            : slv(63 downto 0);
      addrWrapCount    : slv(31 downto 0);
      dispatchCounter  : slv(DISPATCH_COUNTER_BITS_G-1 downto 0);
      -- Completion control / status (from old WorkCompChecker)
      resetCounters    : sl;
      successCounter   : slv(DISPATCH_COUNTER_BITS_G-1 downto 0);
      unsuccessCounter : slv(DISPATCH_COUNTER_BITS_G-1 downto 0);
      -- Completion-counter FSM working state
      compState        : CompStateType;
      status           : slv(4 downto 0);
      workCompSlave    : RoceWorkCompSlaveType;
      -- AXI-Lite slave outputs
      axilReadSlave    : AxiLiteReadSlaveType;
      axilWriteSlave   : AxiLiteWriteSlaveType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      startDispatching => '0',
      len              => (others => '0'),
      rKey             => (others => '0'),
      lKey             => (others => '0'),
      sQpn             => (others => '0'),
      dQpn             => (others => '0'),
      rAddr            => (others => '0'),
      addrWrapCount    => (others => '0'),
      dispatchCounter  => (others => '0'),
      resetCounters    => '0',
      successCounter   => (others => '0'),
      unsuccessCounter => (others => '0'),
      compState        => ST0_IDLE,
      status           => (others => '0'),
      workCompSlave    => ROCE_WORK_COMP_SLAVE_INIT_C,
      axilReadSlave    => AXI_LITE_READ_SLAVE_INIT_C,
      axilWriteSlave   => AXI_LITE_WRITE_SLAVE_INIT_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   -- Internal repack FIFO drain interface (Block A). The FIFO buffers the
   -- inbound PRBS payload (sAxisMaster) and presents it on fifoMaster; the
   -- REPACK FSM (Block B) drives fifoSlave.tReady to consume each beat.
   signal fifoMaster : AxiStreamMasterType;
   signal fifoSlave  : AxiStreamSlaveType;

   ----------------------------------------------------------------------------
   -- REPACK FSM register record (Block B). Separate from the AXI-Lite RegType
   -- so the two processes stay independent. Termination is tLast-driven; there
   -- is intentionally NO globalByteCounter / cross-request state.
   ----------------------------------------------------------------------------
   type RepStateType is (ST0_IDLE, ST1_SEND_PKG);

   -- Drained-byte accumulator width: len is 13-bit (<=8191); 14 bits holds the
   -- accumulated count without overflow when a final 32-byte beat is added on
   -- top of a near-len running total.
   constant REP_BYTE_CNT_W_C : positive := 14;

   type RepRegType is record
      state             : RepStateType;
      reqLatched        : RoceDmaReadReqMasterType;
      first             : sl;
      drainedBytes      : unsigned(REP_BYTE_CNT_W_C-1 downto 0);
      dmaReadReqSlave   : RoceDmaReadReqSlaveType;
      dmaReadRespMaster : RoceDmaReadRespMasterType;
      fifoSlave         : AxiStreamSlaveType;
   end record RepRegType;

   constant REP_INIT_C : RepRegType := (
      state             => ST0_IDLE,
      reqLatched        => ROCE_DMA_READ_REQ_MASTER_INIT_C,
      first             => '1',
      drainedBytes      => (others => '0'),
      dmaReadReqSlave   => ROCE_DMA_READ_REQ_SLAVE_INIT_C,
      dmaReadRespMaster => ROCE_DMA_READ_RESP_MASTER_INIT_C,
      fifoSlave         => AXI_STREAM_SLAVE_INIT_C);

   signal rep   : RepRegType := REP_INIT_C;
   signal repin : RepRegType;

   ----------------------------------------------------------------------------
   -- DISPATCH FSM register record (Block C). Separate from the AXI-Lite RegType;
   -- drives workReqMaster.
   ----------------------------------------------------------------------------
   type DispStateType is (ST0_IDLE, ST1_SENDING);

   type DispRegType is record
      state     : DispStateType;
      count     : slv(DISPATCH_COUNTER_BITS_G-1 downto 0);
      addrCount : slv(DISPATCH_COUNTER_BITS_G-1 downto 0);
      txMaster  : RoceWorkReqMasterType;
   end record DispRegType;

   constant DISP_INIT_C : DispRegType := (
      state     => ST0_IDLE,
      count     => (others => '0'),
      addrCount => (others => '0'),
      txMaster  => ROCE_WORK_REQ_MASTER_INIT_C);

   signal dispR   : DispRegType := DISP_INIT_C;
   signal dispRin : DispRegType;

   -- StartDispatching rising-edge one-shot (surf.SynchronizerEdge output).
   signal startDispatching : sl;

   -- Track previous rAddr to detect a new MR (startZmq restart). Initialised to
   -- all-ones so the very first rAddr write always triggers an addrCount reset.
   signal prevRAddr : slv(63 downto 0) := (others => '1');

begin  -- architecture rtl

   ----------------------------------------------------------------------------
   -- Block A: internal repack FIFO. GEN_SYNC_FIFO_G=true (single roceClk domain,
   -- no CDC); FIFO_ADDR_WIDTH_G default 9 holds >=2 packets for len<=8191.
   -- Backpressures the free-running PRBS source via sAxisSlave (bounded depth).
   ----------------------------------------------------------------------------
   U_RepackFifo : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         GEN_SYNC_FIFO_G     => true,
         FIFO_ADDR_WIDTH_G   => FIFO_ADDR_WIDTH_G,
         SLAVE_AXI_CONFIG_G  => AXIS_CONFIG_G,
         MASTER_AXI_CONFIG_G => AXIS_CONFIG_C)
      port map (
         sAxisClk    => roceClk,
         sAxisRst    => roceRst,
         sAxisMaster => sAxisMaster,   -- external inbound PRBS port
         sAxisSlave  => sAxisSlave,    -- external backpressure to PRBS
         mAxisClk    => roceClk,
         mAxisRst    => roceRst,
         mAxisMaster => fifoMaster,    -- internal drain master
         mAxisSlave  => fifoSlave);    -- internal drain slave (REPACK FSM drives tReady)

   ----------------------------------------------------------------------------
   -- Single merged AXI-Lite register file (Block E).
   --
   -- Register map (the App crossbar ROCE_DMA slot and the PyRogue device
   -- offsets must match these exactly):
   --
   --   Offset  Bits    Access  Name              Field
   --   0x00    [0]     RW      StartDispatching  startDispatching (edge-detected)
   --   0x04    [31:0]  RW      Len               len
   --   0x08    [31:0]  RW      RKey              rKey
   --   0x0C    [31:0]  RW      LKey              lKey
   --   0x10    [23:0]  RW      SQpn              sQpn
   --   0x14    [24:0]  RW      DQpn              dQpn   (UD field; unused by RC WRITE)
   --   0x18    [63:0]  RW      RemAddr           rAddr  (occupies 0x18/0x1C)
   --   0x20    [31:0]  RW      AddrWrapCount     addrWrapCount
   --   0x24    [N:0]   RW      DispatchCounter   dispatchCounter
   --   0x100   [N:0]   RO      SuccessCounter    successCounter
   --   0x104   [N:0]   RO      UnsuccessCounter  unsuccessCounter
   --   0x108   [0]     RW      ResetCounters     resetCounters
   --
   --   The RO status block is based at 0x100 to stay disjoint from the RW block.
   ----------------------------------------------------------------------------
   regComb : process (axilReadMaster, axilWriteMaster, r, workCompMaster) is
      variable v      : RegType;
      variable regCon : AxiLiteEndPointType;
   begin

      -- Latch current state
      v := r;

      -- Determine the transaction type
      axiSlaveWaitTxn(regCon, axilWriteMaster, axilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      -- RW dispatch block
      axiSlaveRegister (regCon, x"000", 0, v.startDispatching);
      axiSlaveRegister (regCon, x"004", 0, v.len);
      axiSlaveRegister (regCon, x"008", 0, v.rKey);
      axiSlaveRegister (regCon, x"00C", 0, v.lKey);
      axiSlaveRegister (regCon, x"010", 0, v.sQpn);
      -- 0x14 DQpn: drives the work-request dQpn (see dispatch FSM). UD-datagram
      -- field; the RC RDMA-WRITE path routes via sQpn, so normally left 0.
      axiSlaveRegister (regCon, x"014", 0, v.dQpn);
      axiSlaveRegister (regCon, x"018", 0, v.rAddr);  -- 64-bit: occupies 0x18/0x1C
      axiSlaveRegister (regCon, x"020", 0, v.addrWrapCount);
      axiSlaveRegister (regCon, x"024", 0, v.dispatchCounter);

      -- RO status block (based at 0x100, disjoint from the RW block)
      axiSlaveRegisterR(regCon, x"100", 0, r.successCounter);
      axiSlaveRegisterR(regCon, x"104", 0, r.unsuccessCounter);
      axiSlaveRegister (regCon, x"108", 0, v.resetCounters);

      -- Closeout: DECERR on unmapped offsets (reject aliased/malformed offsets).
      -- Do NOT relax to OK.
      axiSlaveDefault(regCon, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      -- Registered slave outputs (one-cycle registered)
      axilWriteSlave <= r.axilWriteSlave;
      axilReadSlave  <= r.axilReadSlave;

      ------------------------------------------------------------------------
      -- Block D: completion-counter FSM. Lives in this process so it is the
      -- SINGLE driver of successCounter/unsuccessCounter (the RO offsets
      -- 0x100/0x104 above read from the same r.* record).
      --
      -- status "00000" = success. On a completion, latch the status, then
      -- increment success (if "00000") else unsuccess. A ResetCounters (0x108)
      -- write synchronously clears both counters.
      ------------------------------------------------------------------------

      -- Default: do not accept a completion this cycle.
      v.workCompSlave.ready := '0';

      -- ResetCounters sync-clear.
      if r.resetCounters = '1' then
         v.successCounter   := (others => '0');
         v.unsuccessCounter := (others => '0');
      end if;

      case r.compState is
         ---------------------------------------------------------------------
         when ST0_IDLE =>
            if workCompMaster.valid = '1' then
               v.workCompSlave.ready := '1';
               v.status              := workCompMaster.status;
               v.compState           := ST1_RECEIVED;
            end if;
         ---------------------------------------------------------------------
         when ST1_RECEIVED =>
            if r.status = "00000" then
               v.successCounter   := std_logic_vector(unsigned(r.successCounter) + 1);
            else
               v.unsuccessCounter := std_logic_vector(unsigned(r.unsuccessCounter) + 1);
            end if;
            v.compState := ST0_IDLE;
         ---------------------------------------------------------------------
         when others =>
            v.compState := ST0_IDLE;
      end case;

      -- Completion-handshake output. Combinatorial on v so the one-cycle ready
      -- pulse aligns with the workCompMaster.valid it accepts.
      workCompSlave <= v.workCompSlave;

      -- Register update
      rin <= v;

   end process regComb;

   seq : process (roceClk, roceRst) is
   begin
      if (RST_ASYNC_G) and (roceRst = '1') then
         r         <= REG_INIT_C after TPD_G;
         prevRAddr <= (others => '1') after TPD_G;
      elsif rising_edge(roceClk) then
         if (RST_ASYNC_G = false) and (roceRst = '1') then
            r         <= REG_INIT_C after TPD_G;
            prevRAddr <= (others => '1') after TPD_G;
         else
            r <= rin after TPD_G;
            -- Track previous rAddr so the dispatch FSM can detect a new MR.
            prevRAddr <= r.rAddr after TPD_G;
         end if;
      end if;
   end process seq;

   ----------------------------------------------------------------------------
   -- Block B: tLast-driven REPACK FSM + 290-bit dataStream packing.
   --
   -- Drains exactly ONE tLast-delimited packet per dmaReadReqMaster.valid
   -- (termination is fifoMaster.tLast, not a decremented len counter). Each
   -- response beat packs the 290-bit dataStream:
   --     data(255:0) & byteEn(31:0) & isFirst & isLast
   -- with byteEn = fifoMaster.tKeep(31:0) 1:1. There is no globalByteCounter.
   ----------------------------------------------------------------------------
   repComb : process (dmaReadReqMaster, dmaReadRespSlave, fifoMaster, rep) is
      variable v        : RepRegType;
      variable isFirst  : sl;
      variable beatBytes : unsigned(REP_BYTE_CNT_W_C-1 downto 0);
      variable lenMatch : boolean;
   begin
      -- Latch current state
      v := rep;

      -- Default: do not accept a new request or drain a beat this cycle
      v.dmaReadReqSlave.ready := '0';
      v.fifoSlave.tReady      := '0';

      -- De-assert the response valid once the engine has accepted the beat.
      if dmaReadRespSlave.ready = '1' then
         v.dmaReadRespMaster.valid := '0';
      end if;

      case rep.state is

         ---------------------------------------------------------------------
         when ST0_IDLE =>
            if dmaReadReqMaster.valid = '1' then
               -- Latch the request and accept it for one cycle.
               v.dmaReadReqSlave.ready := '1';
               v.reqLatched            := dmaReadReqMaster;
               -- Reset the drained-byte accumulator and arm the isFirst flag.
               v.drainedBytes          := (others => '0');
               v.first                 := '1';
               v.state                 := ST1_SEND_PKG;
            end if;

         ---------------------------------------------------------------------
         when ST1_SEND_PKG =>
            -- Drain a beat only when the FIFO has data AND the response slot is
            -- free (back-to-back beats gate on the engine accepting the prior beat).
            if (fifoMaster.tValid = '1') and (v.dmaReadRespMaster.valid = '0') then

               -- isFirst flag (asserted on the first drained beat, then cleared).
               isFirst := '0';
               if rep.first = '1' then
                  isFirst := '1';
                  v.first := '0';
               end if;

               -- Per-beat valid-byte count (popcount of tKeep).
               beatBytes := to_unsigned(getTKeep(fifoMaster.tKeep, AXIS_CONFIG_C), REP_BYTE_CNT_W_C);

               -- 290-bit concatenation: data(255:0) & byteEn(31:0) & isFirst &
               -- isLast, byteEn = tKeep 1:1.
               --
               -- endianSwap() reverses the 32 byte lanes so the RDMA payload is
               -- little-endian (tData(7:0) -> first payload byte) — matching the
               -- surf/rogue tData convention the host PrbsRx(width=256) expects.
               -- The direct (un-swapped) mapping serialized big-endian and failed
               -- the host PRBS check on every frame.
               v.dmaReadRespMaster.dataStream :=
                  endianSwap(fifoMaster.tData(255 downto 0)) &
                  fifoMaster.tKeep(31 downto 0) &
                  isFirst &
                  fifoMaster.tLast;

               -- Echo the latched request fields (DmaTestPatternServer.vhd:182-184).
               v.dmaReadRespMaster.initiator := rep.reqLatched.initiator;
               v.dmaReadRespMaster.sQpn      := rep.reqLatched.sQpn;
               v.dmaReadRespMaster.wrId      := rep.reqLatched.wrId;
               v.dmaReadRespMaster.valid     := '1';

               -- Consume the beat from the FIFO and accumulate drained bytes.
               v.fifoSlave.tReady := '1';
               v.drainedBytes     := rep.drainedBytes + resize(beatBytes, REP_BYTE_CNT_W_C);

               -- On tLast: flag isRespErr if the drained byte count != requested
               -- len, on EOFE, or on a partial last beat. The endianSwap above is
               -- only correct for full 32-byte beats (byteEn is not reversed); a
               -- partial last beat (tKeep /= all-ones) would corrupt the payload,
               -- so reject it loudly. SsiPrbsTx only emits full beats, so the
               -- partial-beat term never fires here — it guards other sources.
               if fifoMaster.tLast = '1' then
                  lenMatch :=
                     (rep.drainedBytes + resize(beatBytes, REP_BYTE_CNT_W_C)) =
                     resize(unsigned(rep.reqLatched.len), REP_BYTE_CNT_W_C);
                  v.dmaReadRespMaster.isRespErr :=
                     ite(not lenMatch, '1', '0') or
                     ssiGetUserEofe(AXIS_CONFIG_C, fifoMaster) or
                     ite(fifoMaster.tKeep(31 downto 0) = x"FFFFFFFF", '0', '1');
                  v.state := ST0_IDLE;
               end if;
            end if;

         ---------------------------------------------------------------------
         when others =>
            v := REP_INIT_C;

      end case;

      -- Registered outputs (one-cycle registered).
      dmaReadReqSlave   <= rep.dmaReadReqSlave;
      dmaReadRespMaster <= rep.dmaReadRespMaster;
      fifoSlave         <= v.fifoSlave;

      -- Register update
      repin <= v;

   end process repComb;

   repSeq : process (roceClk, roceRst) is
   begin
      if (RST_ASYNC_G) and (roceRst = '1') then
         rep <= REP_INIT_C after TPD_G;
      elsif rising_edge(roceClk) then
         if (RST_ASYNC_G = false) and (roceRst = '1') then
            rep <= REP_INIT_C after TPD_G;
         else
            rep <= repin after TPD_G;
         end if;
      end if;
   end process repSeq;

   ----------------------------------------------------------------------------
   -- Block C: dispatch FSM + work-request issue.
   --
   -- StartDispatching (0x00) is a level register; the dispatch FSM triggers on
   -- its RISING EDGE via surf.SynchronizerEdge (single roceClk domain). On the
   -- edge the FSM issues exactly DispatchCounter (0x24) RDMA-WRITE-with-immediate
   -- work requests, one per accepted workReqSlave handshake, reading the dispatch
   -- fields from the register file.
   --
   -- dQpn is driven from register 0x14 (DQpn). It is a UD-datagram field; the
   -- RC RDMA-WRITE path routes via sQpn + the connection QP context, so dQpn is
   -- normally left 0 and does not affect the WRITE.
   ----------------------------------------------------------------------------
   U_StartEdge : entity surf.SynchronizerEdge
      generic map (
         TPD_G         => TPD_G,
         BYPASS_SYNC_G => true)         -- single roceClk domain, no CDC
      port map (
         clk        => roceClk,
         dataIn     => r.startDispatching,
         risingEdge => startDispatching);

   dispComb : process (dispR, prevRAddr, r, startDispatching, workReqSlave) is
      variable v         : DispRegType;
      variable idPadding : slv(63 downto DISPATCH_COUNTER_BITS_G) := (others => '0');
      variable nextAddr  : unsigned(DISPATCH_COUNTER_BITS_G-1 downto 0);
   begin
      -- Latch current state
      v := dispR;

      -- De-assert the work-request valid once the engine has accepted it.
      if workReqSlave.ready = '1' then
         v.txMaster.valid := '0';
      end if;

      case dispR.state is

         ---------------------------------------------------------------------
         when ST0_IDLE =>
            -- Reset addrCount when rAddr changes (new MR after startZmq restart);
            -- addrCount persists across bursts within a session.
            if r.rAddr /= prevRAddr then
               v.addrCount := (others => '0');
            end if;
            -- The StartDispatching rising-edge one-shot launches the burst.
            if startDispatching = '1' then
               v.state := ST1_SENDING;
            end if;

         ---------------------------------------------------------------------
         when ST1_SENDING =>
            if v.txMaster.valid = '0' then
               -- id = zero-pad & (count + 1).
               v.txMaster.id     := idPadding & std_logic_vector(unsigned(dispR.count) + 1);
               v.txMaster.opCode := x"1";
               v.txMaster.flags  := "00010";  -- RDMA Write with Immediate
               -- rAddr = rAddr + addrCount*len (product resized to 64 bits).
               v.txMaster.rAddr  := std_logic_vector(unsigned(r.rAddr) +
                                       resize(unsigned(dispR.addrCount) * unsigned(r.len), 64));
               v.txMaster.rKey   := r.rKey;
               v.txMaster.len    := r.len;
               v.txMaster.lAddr  := (others => '0');
               v.txMaster.lKey   := r.lKey;
               v.txMaster.sQpn   := r.sQpn;
               v.txMaster.solicited := '0';
               v.txMaster.comp   := (others => '0');
               v.txMaster.swap   := (others => '0');
               -- Set immediate data channel ID to 1 so the rogue StreamWriter routes
               -- incoming RDMA frames to channel 1 (dataWriter.getChannel(1)).
               -- Bits [7:0] of immDt are decoded by Server.cpp as the rogue stream
               -- channel; channel 0 is reserved for the UDP/RSSI stream.
               v.txMaster.immDt  := std_logic_vector(to_unsigned(1, v.txMaster.immDt'length));
               v.txMaster.rKeyToInv := (others => '0');
               v.txMaster.srqn   := (others => '0');
               -- dQpn from register 0x14 (UD-datagram field; unused by the RC
               -- RDMA-WRITE path, which routes via sQpn, so normally 0).
               v.txMaster.dQpn   := r.dQpn;
               v.txMaster.qKey   := (others => '0');
               v.txMaster.valid  := '1';

               -- Advance addrCount, wrapping at addrWrapCount.
               nextAddr := unsigned(dispR.addrCount) + 1;
               if nextAddr >= unsigned(r.addrWrapCount(DISPATCH_COUNTER_BITS_G-1 downto 0)) then
                  v.addrCount := (others => '0');
               else
                  v.addrCount := std_logic_vector(nextAddr);
               end if;

               -- Advance the dispatch counter; issue exactly DispatchCounter
               -- work requests (one per accepted handshake) then return to idle.
               if unsigned(dispR.count) < unsigned(r.dispatchCounter) - 1 then
                  v.count := std_logic_vector(unsigned(v.count) + 1);
                  v.state := ST1_SENDING;
               else
                  v.count := (others => '0');
                  v.state := ST0_IDLE;
               end if;
            end if;

         ---------------------------------------------------------------------
         when others =>
            v := DISP_INIT_C;

      end case;

      -- Registered work-request master output.
      workReqMaster <= dispR.txMaster;

      -- Register update
      dispRin <= v;

   end process dispComb;

   dispSeq : process (roceClk, roceRst) is
   begin
      if (RST_ASYNC_G) and (roceRst = '1') then
         dispR <= DISP_INIT_C after TPD_G;
      elsif rising_edge(roceClk) then
         if (RST_ASYNC_G = false) and (roceRst = '1') then
            dispR <= DISP_INIT_C after TPD_G;
         else
            dispR <= dispRin after TPD_G;
         end if;
      end if;
   end process dispSeq;

end architecture rtl;
