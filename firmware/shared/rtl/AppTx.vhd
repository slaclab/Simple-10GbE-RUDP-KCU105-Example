-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Application TX Firmware Module
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
use surf.SsiPkg.all;
use surf.RssiPkg.all;

entity AppTx is
   generic (
      TPD_G        : time    := 1 ns;
      SIMULATION_G : boolean := false);
   port (
      -- Clock and Reset
      axilClk         : in  sl;
      axilRst         : in  sl;
      -- AXI-Stream Interface
      txMaster        : out AxiStreamMasterType;
      txSlave         : in  AxiStreamSlaveType;
      -- AXI-Lite Interface
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType;
      -- LED Output Port
      led_out           : out slv(1 downto 0));
end AppTx;

architecture rtl of AppTx is

   type StateType is (
      IDLE_S,
      MOVE_S);

   type RegType is record
      frameSize      : slv(31 downto 0);
      sendFrame      : slv(31 downto 0);
      frameCnt       : slv(31 downto 0);
      frameMax       : slv(31 downto 0);
      wordCnt        : slv(31 downto 0);
      wordMax        : slv(31 downto 0);
      continousMode  : sl;
      txMaster       : AxiStreamMasterType;
      axilReadSlave  : AxiLiteReadSlaveType;
      axilWriteSlave : AxiLiteWriteSlaveType;
      state          : StateType;
      led            : slv(1 downto 0);
      toggleRate     : slv(31 downto 0);
      toggleCounter  : slv(31 downto 0);
   end record RegType;
   constant REG_INIT_C : RegType := (
      frameSize      => x"0001_ffff",  -- Default Optimized for max. bandwidth (~9.8 Gb/s) and max. frame rate (~1.2 kHz)
      sendFrame      => (others => '0'),
      frameCnt       => (others => '0'),
      frameMax       => (others => '0'),
      wordCnt        => (others => '0'),
      wordMax        => (others => '0'),
      continousMode  => '0',
      txMaster       => axiStreamMasterInit(RSSI_AXIS_CONFIG_C),
      axilReadSlave  => AXI_LITE_READ_SLAVE_INIT_C,
      axilWriteSlave => AXI_LITE_WRITE_SLAVE_INIT_C,
      state          => IDLE_S,
      led            => "11",
      toggleRate     => x"1111_1111",
      toggleCounter  => (others => '0')); -- toggles every ~2.5 sec

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

begin

   comb : process (axilReadMaster, axilRst, axilWriteMaster, r, txSlave) is
      variable v      : RegType;
      variable axilEp : AxiLiteEndPointType;
   begin
      -- Latch the current value
      v := r;

      ----------------------------------------------------------------------
      --                AXI-Lite Register Logic
      ----------------------------------------------------------------------

      -- Determine the transaction type
      axiSlaveWaitTxn(axilEp, axilWriteMaster, axilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      -- Map the read registers
      axiSlaveRegister (axilEp, x"000", 0, v.frameSize);  -- Units of 64-bit words
      axiSlaveRegister (axilEp, x"004", 0, v.sendFrame);  -- Write Only for sending burst of frames
      axiSlaveRegisterR(axilEp, x"008", 0, r.frameCnt);  -- Read Only for monitoring bursting status
      axiSlaveRegisterR(axilEp, x"00C", 0, r.wordCnt);  -- Read Only for monitoring bursting status

      axiSlaveRegister (axilEp, x"010", 0, v.continousMode);  -- Bursting Continuously Flag

      -- R/W access for LED control
      axiSlaveRegister (axilEp, x"014", 0, v.led);
      
      -- toggleRate reg
      axiSlaveRegister (axilEp, x"018", 0, v.toggleRate);
      
      -- counter reg
      axiSlaveRegister (axilEp, x"01C", 0, v.toggleCounter);

      -- Closeout the transaction
      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      -- counter for toggleRate
      v.toggleCounter := r.toggleCounter + 1;

      -- conditionals for toggleRate
      if (v.toggleCounter = v.toggleRate) then
         v.led := not r.led;
         v.toggleCounter := (others => '0');
      end if;
      
      if (v.toggleRate /= r.toggleRate) then
         v.toggleCounter := (others => '0');
      end if;

      ----------------------------------------------------------------------
      --                AXI Stream TX Logic
      ----------------------------------------------------------------------

      -- AXI Stream Flow Control
      if (txSlave.tReady = '1') then
         v.txMaster := axiStreamMasterInit(RSSI_AXIS_CONFIG_C);
      end if;

      case r.state is
         ----------------------------------------------------------------------
         when IDLE_S =>
            -- Wait for packet send request
            if (r.sendFrame /= 0) or (r.continousMode = '1') then

               -- Latch the frameSize (in cause software changes it during streaming)
               if r.frameSize /= 0 then
                  v.wordMax := r.frameSize-1;   
               else
                  v.wordMax := r.frameSize;
               end if;

               -- Check for mode
               if (r.continousMode = '1') then

                  -- 1 frame (zero inclusive)
                  v.frameMax := (others => '0');

               else

                  -- Latch the sendFrame (in cause software changes it during streaming)
                  if r.sendFrame /= 0 then
                     v.frameMax := r.sendFrame-1;
                  else
                     v.frameMax := r.sendFrame;
                  end if;

                  -- Reset the command value
                  v.sendFrame := (others => '0');

               end if;

               -- Next state
               v.state := MOVE_S;

            end if;
         ----------------------------------------------------------------------
         when MOVE_S =>
            -- Check if ready to move data
            if (v.txMaster.tValid = '0') then

               -- Send the data
               v.txMaster.tValid             := '1';
               v.txMaster.tData(63 downto 0) := resize(r.wordCnt, 64);

               -- Check for Start Of Frame (SOF)
               if (r.wordCnt = 0) then

                  -- Overwrite first word with frame count index (simple header)
                  v.txMaster.tData(63 downto 0) := resize(r.frameCnt, 64);

                  -- Set the SOF bit
                  ssiSetUserSof(RSSI_AXIS_CONFIG_C, v.txMaster, '1');

               end if;

               -- Check for End of Frame (EOF)
               if (r.wordCnt = r.wordMax) then

                  -- Set the EOF bit
                  v.txMaster.tLast := '1';

                  -- Reset the counter
                  v.wordCnt := (others => '0');

                  -- Check for last burst frame
                  if (r.frameCnt = r.frameMax) then

                     -- Reset the counter
                     v.frameCnt := (others => '0');

                     -- Next state
                     v.state := IDLE_S;

                  else
                     -- Increment the counter
                     v.frameCnt := r.frameCnt + 1;
                  end if;

               else
                  -- Increment the counter
                  v.wordCnt := r.wordCnt + 1;
               end if;

            end if;
      ----------------------------------------------------------------------
      end case;

      ----------------------------------------------------------------------

      -- Outputs
      axilWriteSlave <= r.axilWriteSlave;
      axilReadSlave  <= r.axilReadSlave;
      txMaster       <= r.txMaster;
      led_out        <= r.led;

      ----------------------------------------------------------------------

      -- Reset
      if (axilRst = '1') then
         v := REG_INIT_C;
      end if;

      -- Register the variable for next clock cycle
      rin <= v;

   end process comb;

   seq : process (axilClk) is
   begin
      if rising_edge(axilClk) then
         r <= rin after TPD_G;
      end if;
   end process seq;

end rtl;
