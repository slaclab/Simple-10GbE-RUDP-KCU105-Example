import setupLibPaths
import sys
import logging
import time
import argparse
import pyrogue as pr
import pyrogue.interfaces


if __name__ == "__main__":

    # Convert str to bool
    argBool = lambda s: s.lower() in ['true', 't', 'yes', '1']

    # Set the argument parser
    parser = argparse.ArgumentParser(description='Dispatch RDMA WRITE-with-Immediate packets')

    parser.add_argument(
        "--addr",
        type    = str,
        required= False,
        default = 'localhost',
        help    = "ZMQ server address",
    )
    parser.add_argument(
        "--port",
        type    = int,
        required= False,
        default = 9099,
        help    = "ZMQ server port",
    )
    parser.add_argument(
        "--sim",
        action  = 'store_true',
        help    = "Simulation mode",
    )
    parser.add_argument(
        "--cases",
        required= False,
        default = 1,
        type    = int,
        help    = "Number of packets to send",
    )
    # Get the arguments
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format = '%(levelname)s:%(name)s:%(message)s',
        stream = sys.stdout,
    )
    log = logging.getLogger('dispatch')
    log.setLevel(logging.DEBUG)

    #################################################################
    with pr.interfaces.VirtualClient(
            addr = args.addr,
            port = args.port,
    ) as client:

        rx   = client.root.rdmaRx
        root = client.root

        # ----------------------------------------------------------------
        # Validate connection state
        # ----------------------------------------------------------------
        state = rx.ConnectionState.get()
        if state != 'Connected':
            log.error(f'RoCEv2 not connected (state={state}) — aborting')
            sys.exit(1)

        # ----------------------------------------------------------------
        # Retrieve MR parameters from rogue local variables
        # ----------------------------------------------------------------
        rx_queue_depth = rx.RxQueueDepth.get()
        max_payload    = rx.MaxPayload.get()
        mr_len         = rx_queue_depth * max_payload
        remQpn         = rx.HostQpn.get()
        mrRKey         = rx.MrRkey.get()
        mrAddr         = rx.MrAddr.get()
        locKey         = rx.FpgaLkey.get()

        # Payload = MaxPayload so MR slots are always fully used
        # and the FPGA writes contiguously with no gaps
        payload = max_payload
        addr_wrap = rx_queue_depth  # = mr_len // payload since payload == max_payload

        # ----------------------------------------------------------------
        # Print connection info
        # ----------------------------------------------------------------
        log.info('--- RoCEv2 connection parameters ---')
        log.info(f'  ConnectionState : {rx.ConnectionState.get()}')
        log.info(f'  Host QPN        : {hex(remQpn)}')
        log.info(f'  Host GID        : {rx.HostGid.get()}')
        log.info(f'  Host RQ PSN     : {hex(rx.HostRqPsn.get())}')
        log.info(f'  Host SQ PSN     : {hex(rx.HostSqPsn.get())}')
        log.info(f'  MR addr         : {hex(mrAddr)}')
        log.info(f'  MR rkey         : {hex(mrRKey)}')
        log.info(f'  FPGA lkey       : {hex(locKey)}')
        log.info(f'  FPGA QPN        : {hex(rx.FpgaQpn.get())}')
        log.info(f'  FPGA GID        : {rx.FpgaGid.get()}')
        log.info(f'  MaxPayload      : {max_payload}')
        log.info(f'  RxQueueDepth    : {rx_queue_depth}')
        log.info(f'  MrLen           : {mr_len}')
        log.info(f'  Payload (= MaxPayload) : {payload}')
        log.info(f'  AddrWrapCount   : {addr_wrap}')
        log.info('------------------------------------')

        # ----------------------------------------------------------------
        # Set UDP engine destination
        # ----------------------------------------------------------------
        root.Core.UdpEngine.ClientRemotePort[0].set(4791)
        root.Core.UdpEngine.ClientRemoteIp[0].set("192.168.2.100")

        # ----------------------------------------------------------------
        # Reset checker counters
        # ----------------------------------------------------------------
        log.info('Resetting counters...')
        root.App.RoceChecker.ResetCounters.set(0)
        root.App.RoceChecker.ResetCounters.set(1)
        root.App.RoceChecker.ResetCounters.set(0)

        # ----------------------------------------------------------------
        # Configure dispatcher
        # ----------------------------------------------------------------
        root.App.RoceDispatcher.Len.set(payload)
        root.App.RoceDispatcher.DispatchCounter.set(args.cases)
        root.App.RoceDispatcher.RKey.set(mrRKey)
        root.App.RoceDispatcher.RemAddr.set(mrAddr)
        root.App.RoceDispatcher.AddrWrapCount.set(addr_wrap)

        root.App.RoceDispatcher.SQpn.set(remQpn)
        root.App.RoceDispatcher.LKey.set(locKey)

        # ----------------------------------------------------------------
        # Trigger dispatch
        # ----------------------------------------------------------------
        log.info(f'Dispatching {args.cases} packet(s) of {payload} bytes...')
        root.App.RoceDispatcher.StartDispatching.set(0)
        root.App.RoceDispatcher.StartDispatching.set(1)
        root.App.RoceDispatcher.StartDispatching.set(0)

        # ----------------------------------------------------------------
        # Wait and check results
        # ----------------------------------------------------------------
        time.sleep(2)
        success = root.App.RoceChecker.SuccessCounter.get()
        log.info(f'Correctly received {success} / {args.cases} packet(s)')
        if success != args.cases:
            log.warning(f'{args.cases - success} packet(s) missing or errored')

