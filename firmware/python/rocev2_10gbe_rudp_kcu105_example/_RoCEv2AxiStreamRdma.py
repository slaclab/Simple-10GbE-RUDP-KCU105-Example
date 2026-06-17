#-----------------------------------------------------------------------------
# This file is part of the 'Simple-10GbE-RUDP-KCU105-Example'. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the 'Simple-10GbE-RUDP-KCU105-Example', including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------

import pyrogue as pr

class RoCEv2AxiStreamRdma(pr.Device):
    def __init__( self,
                  dispatchBits=24,
                  **kwargs):
        super().__init__(**kwargs)

        self.add(pr.RemoteVariable(
            name         = 'DispatchEnable',
            description  = 'Arm continuous event-driven dispatch: while set, the FW issues '
                           'one RDMA SEND-with-immediate per complete PRBS packet buffered '
                           'in the repack FIFO. Set with SsiPrbsTx.TxEn=True for a '
                           'self-sustaining stream; clear to stop',
            offset       = 0x00,
            bitSize      = 1,
            bitOffset    = 0,
            base         = pr.Bool,
            mode         = 'RW',
        ))

        self.add(pr.RemoteVariable(
            name         = 'Len',
            description  = 'Bytes per RDMA SEND-with-immediate',
            offset       = 0x04,
            bitSize      = 32,
            disp         = '{:d}',
            mode         = 'RW',
        ))

        self.add(pr.RemoteVariable(
            name         = 'RKey',
            description  = 'Legacy RETH remote key — UNUSED by RDMA SEND (FW drives rKey=0); '
                           'retained for register-map stability',
            offset       = 0x08,
            bitSize      = 32,
            mode         = 'RW',
        ))

        self.add(pr.RemoteVariable(
            name         = 'LKey',
            description  = 'Local key for the RDMA SEND',
            offset       = 0x0C,
            bitSize      = 32,
            mode         = 'RW',
        ))

        self.add(pr.RemoteVariable(
            name         = 'SQpn',
            description  = 'Source queue-pair number',
            offset       = 0x10,
            bitSize      = 24,
            mode         = 'RW',
        ))

        self.add(pr.RemoteVariable(
            name         = 'DQpn',
            description  = 'Destination queue-pair number (UD-datagram field). The RC '
                           'RDMA-WRITE path routes via SQpn + the QP context, so this is '
                           'normally left 0',
            offset       = 0x14,
            bitSize      = 24,
            mode         = 'RW',
        ))

        self.add(pr.RemoteVariable(
            name         = 'RemAddr',
            description  = 'Legacy RETH remote address (64-bit, 0x18/0x1C) — UNUSED by RDMA '
                           'SEND (FW drives rAddr=0); retained for register-map stability',
            offset       = 0x18,
            bitSize      = 64,
            mode         = 'RW',
        ))

        self.add(pr.RemoteVariable(
            name         = 'AddrWrapCount',
            description  = 'Number of immDt slot increments before wrapping back to 0 (the '
                           'free-running ring position stamped in the immediate)',
            offset       = 0x20,
            bitSize      = 32,
            mode         = 'RW',
        ))

        # Flow control is native FW<->NIC: the FW dispatches RDMA-SEND-with-immediate
        # (two-sided), so a full host recv queue makes the NIC RNR-NAK; the blue-rdma
        # SQ stalls/retries (rnr_retry=7) and backpressures the dispatcher. There is
        # NO software credit register in the real-time path (the legacy CreditWindow /
        # CreditConsumed registers at 0x24/0x28 are removed).

        # RO status block (based at 0x100, disjoint from the RW block) ---------

        self.add(pr.RemoteVariable(
            name         = 'SuccessCounter',
            description  = 'Count of successful completions',
            offset       = 0x100,
            bitSize      = dispatchBits,
            mode         = 'RO',
            pollInterval = 1,
            disp         = '{:d}',
        ))

        self.add(pr.RemoteVariable(
            name         = 'UnsuccessCounter',
            description  = 'Count of unsuccessful completions',
            offset       = 0x104,
            bitSize      = dispatchBits,
            mode         = 'RO',
            pollInterval = 1,
            disp         = '{:d}',
        ))

        self.add(pr.RemoteCommand(
            name        = 'ResetCounters',
            description = 'Strobe to clear the Success/Unsuccess counters. toggle (1->0) drives the FW level-clear one-shot',
            offset      = 0x108,
            bitSize     = 1,
            bitOffset   = 0,
            base        = pr.UInt,
            function    = pr.RemoteCommand.toggle,
        ))
