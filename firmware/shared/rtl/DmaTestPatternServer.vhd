-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Dma server to inject a test pattern
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
use ieee.numeric_std.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.SsiPkg.all;
use surf.RoCEv2Pkg.all;

entity DmaTestPatternServer is
   generic (
      TPD_G       : time    := 1 ns;
      RST_ASYNC_G : boolean := false);
   port (
      roceClk           : in  sl;
      roceRst           : in  sl;
      dmaReadReqMaster  : in  RoceDmaReadReqMasterType;
      dmaReadReqSlave   : out RoceDmaReadReqSlaveType;
      dmaReadRespMaster : out RoceDmaReadRespMasterType;
      dmaReadRespSlave  : in  RoceDmaReadRespSlaveType);
end entity DmaTestPatternServer;

architecture rtl of DmaTestPatternServer is

   type RegState is (st0_idle, st1_send_pkg);

   type RegType is record
      state             : RegState;
      reqLatched        : RoceDmaReadReqMasterType;
      -- Global byte counter — persists across requests for continuous pattern
      globalByteCounter : unsigned(7 downto 0);
      -- Running beat offset within current request
      byteAddr          : unsigned(63 downto 0);
      first             : boolean;
      txRespMaster      : RoceDmaReadRespMasterType;
      rxReqSlave        : RoceDmaReadReqSlaveType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      state             => st0_idle,
      reqLatched        => ROCE_DMA_READ_REQ_MASTER_INIT_C,
      globalByteCounter => (others => '0'),
      byteAddr          => (others => '0'),
      first             => true,
      txRespMaster      => ROCE_DMA_READ_RESP_MASTER_INIT_C,
      rxReqSlave        => ROCE_DMA_READ_REQ_SLAVE_INIT_C
      );

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   constant AXI_STREAM_CONFIG_C : AxiStreamConfigType := (
      TSTRB_EN_C    => false,
      TDATA_BYTES_C => 38,
      TDEST_BITS_C  => 0,
      TID_BITS_C    => 0,
      TKEEP_MODE_C  => TKEEP_NORMAL_C,
      TUSER_BITS_C  => 0,
      TUSER_MODE_C  => TUSER_NORMAL_C
      );

   signal s_sAxisSlave       : AxiStreamSlaveType;
   signal s_mAxisMaster      : AxiStreamMasterType;
   signal s_dmaReadReqSlave  : RoceDmaReadReqSlaveType;
   signal s_dmaReadReqMaster : RoceDmaReadReqMasterType;

begin

   -----------------------------------------------------------------------------
   -- FIFO of requests
   -----------------------------------------------------------------------------
   AxiStreamFifoV2_1 : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         GEN_SYNC_FIFO_G     => true,
         FIFO_ADDR_WIDTH_G   => 4,
         SLAVE_AXI_CONFIG_G  => AXI_STREAM_CONFIG_C,
         MASTER_AXI_CONFIG_G => AXI_STREAM_CONFIG_C)
      port map (
         sAxisClk    => RoceClk,
         sAxisRst    => RoceRst,
         sAxisMaster => DmaReadReqToAxiStreamMaster(dmaReadReqMaster),
         sAxisSlave  => s_sAxisSlave,
         mAxisClk    => RoceClk,
         mAxisRst    => RoceRst,
         mAxisMaster => s_mAxisMaster,
         mAxisSlave  => DmaReadReqToAxiStreamSlave(s_dmaReadReqSlave)
         );

   dmaReadReqSlave    <= AxiStreamToDmaReadReqSlave(s_sAxisSlave);
   s_dmaReadReqMaster <= AxiStreamToDmaReadReqMaster(s_mAxisMaster);

   -----------------------------------------------------------------------------
   -- Combinatorial process
   -----------------------------------------------------------------------------
   comb : process (dmaReadRespSlave, r, s_dmaReadReqMaster) is
      variable v          : RegType;
      variable isFirst    : sl;
      variable isLast     : sl;
      variable byteEn     : slv(AXI_STREAM_MAX_TKEEP_WIDTH_C-1 downto 0);
      variable dataStream : slv(255 downto 0);
      variable len        : natural;
      variable beatBytes  : natural;
   begin
      v := r;

      v.rxReqSlave.ready := '0';

      if dmaReadRespSlave.ready = '1' then
         v.txRespMaster.valid := '0';
      end if;

      case r.state is

         -----------------------------------------------------------------------
         when st0_idle =>
            if s_dmaReadReqMaster.valid = '1' then
               v.rxReqSlave.ready := '1';
               v.reqLatched       := s_dmaReadReqMaster;
               -- Do NOT seed byteAddr from startAddr — use globalByteCounter
               -- so the pattern is continuous across frames
               v.byteAddr         := (others => '0');
               v.state            := st1_send_pkg;
            end if;

         -----------------------------------------------------------------------
         when st1_send_pkg =>
            if v.txRespMaster.valid = '0' then

               -- isFirst flag
               isFirst := '0';
               if r.first then
                  isFirst := '1';
                  v.first := false;
               end if;

               -- How many valid bytes in this beat?
               len := to_integer(unsigned(r.reqLatched.len));
               if len < 33 then
                  beatBytes := len;
                  isLast    := '1';
               else
                  beatBytes := 32;
                  isLast    := '0';
               end if;

               -- Fill dataStream using globalByteCounter + beat offset.
               -- byte i gets value (globalByteCounter + byteAddr + i) mod 256.
               for i in 0 to 31 loop
                  dataStream((31-i)*8 + 7 downto (31-i)*8) :=
                     std_logic_vector(
                        (r.globalByteCounter +
                         resize(r.byteAddr, 8) +
                         to_unsigned(i, 8))
                        );
               end loop;

               -- byteEnable
               byteEn := (others => '0');
               for i in 0 to 31 loop
                  if i < beatBytes then
                     byteEn(i) := '1';
                  end if;
               end loop;

               v.txRespMaster.dataStream := dataStream & byteEn(31 downto 0) & isFirst & isLast;
               v.txRespMaster.initiator  := r.reqLatched.initiator;
               v.txRespMaster.sQpn       := r.reqLatched.sQpn;
               v.txRespMaster.wrId       := r.reqLatched.wrId;
               v.txRespMaster.isRespErr  := '0';
               v.txRespMaster.valid      := '1';

               if isLast = '0' then
                  -- Advance beat offset and remaining length
                  v.byteAddr := r.byteAddr + 32;
                  v.reqLatched.len := std_logic_vector(
                     unsigned(r.reqLatched.len) - 32
                     );
                  v.state := st1_send_pkg;
               else
                  -- Advance global counter by the full payload length of this request
                  v.globalByteCounter := r.globalByteCounter +
                                         resize(unsigned(r.reqLatched.len) +
                                                resize(r.byteAddr, 13), 8);
                  v.state := st0_idle;
                  v.first := true;
               end if;

            end if;

         -----------------------------------------------------------------------
         when others =>
            v := REG_INIT_C;

      end case;

      s_dmaReadReqSlave <= v.rxReqSlave;
      dmaReadRespMaster <= r.txRespMaster;
      rin               <= v;

   end process comb;

   -----------------------------------------------------------------------------
   -- Sequential process
   -----------------------------------------------------------------------------
   seq : process (RoceClk, RoceRst) is
   begin
      if (RST_ASYNC_G) and (RoceRst = '1') then
         r <= REG_INIT_C after TPD_G;
      elsif rising_edge(RoceClk) then
         if (RST_ASYNC_G = false and RoceRst = '1') then
            r <= REG_INIT_C after TPD_G;
         else
            r <= rin after TPD_G;
         end if;
      end if;
   end process seq;

end architecture rtl;
