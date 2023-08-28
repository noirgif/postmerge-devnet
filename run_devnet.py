#!/usr/bin/env python3

import itertools
import os
import shutil
import subprocess
import signal
from time import sleep
from routine import retry, check_error

from web3 import Web3, IPCProvider
from beacon import BeaconNode, PrysmNode, TekuNode
from validator import PrysmValidator
from eth_executor import GethNode
from node_config import NodeConfig, NodeConfigBuilder

from port_assignment import beacon_port, beacon_grpc_port, beacon_p2p_tcp_port, beacon_p2p_udp_port, geth_peer_port, geth_http_port, geth_ws_port, geth_authrpc_port, validator_grpc_port, validator_rpc_port


def setup(config: NodeConfig):
    config.devnet_path.mkdir(exist_ok=True)
    os.chdir(config.devnet_path)

    with open('config.yml', 'w') as f:
        f.write(config.config_yml)

    with open('genesis.json', 'w') as f:
        f.write(config.genesis_json)


def setup_node(no, config: NodeConfig):
    if no < 0 or no >= config.num_nodes:
        raise ValueError(
            f"Node number must be between 0 and {config.num_nodes-1} (inclusive)")

    node_path = config.node_path[no]
    geth_path = config.geth_path[no]

    node_path.mkdir(exist_ok=True)

    print(f"Initializing node {no}...")

    # Before starting the beacon node, we need to generate the genesis state for it
    if not (config.devnet_path / 'genesis.ssz').exists():
        print('Generating genesis state for node', no, '...')
        prysmctl_cmd = [
            'prysmctl',
            'testnet',
            'generate-genesis',
            '--fork=bellatrix',
            '--num-validators=64',
            f'--output-ssz={config.devnet_path / "genesis.ssz"}',
            f'--chain-config-file={config.devnet_path / "config.yml"}',
            f'--geth-genesis-json-in={config.devnet_path / "genesis.json"}',
            f'--geth-genesis-json-out={config.devnet_path / "genesis.json"}',
        ]

        retry(lambda: subprocess.run(prysmctl_cmd).returncode == 0)

    subprocess.run(['geth', '--datadir=' + str(geth_path), f'--db.engine={config.db_engine}',
                   'init', str(config.devnet_path / 'genesis.json')], capture_output=True, text=True)

    # copy key to the geth directory
    shutil.copy(config.key_dir / f'key{no}.json', geth_path / 'keystore' / 'key.json')

    with open(node_path / "jwt.hex", 'w') as f:
        f.write(subprocess.run(['openssl', 'rand', '-hex', '32'],
                capture_output=True, text=True).stdout.strip())

def start_node(no, config: NodeConfig) -> list[subprocess.Popen]:
    """Starts a node with the given number
    Returns the processes for geth, beacon and validator"""

    if no < 0 or no >= config.num_nodes:
        raise ValueError(
            f"Node number must be between 0 and {config.num_nodes-1} (inclusive)")

    # start geth node
    geth_proc = GethNode(no, config).run()

    # Add geth node to peers list and connect it to existing nodes
    ipc_path = config.geth_path[no] / 'geth.ipc'
    retry(lambda: ipc_path.exists())
    node = Web3(IPCProvider(str(ipc_path)))
    for peer in config.geth_peers:
        if node.geth.admin.add_peer(peer):
            print('Successfully added peer', peer)
        else:
            print('Failed to connect to peer', peer)
    enodeUrl = node.geth.admin.node_info()['enode']
    config.geth_peers.append(enodeUrl)

    # start beacon node
    beacon : BeaconNode = TekuNode(no, config)
    beacon_proc = beacon.run()
    
    # check if beacon node is running
    sleep(3)
    if check_error([beacon_proc]) != 0:
        print("Beacon node not running")
        with open(beacon.log_path, 'r') as f:
            print(f.read())
        return []

    # start validator node
    validator_proc = None
    if no == 0:
        validator_proc = PrysmValidator(no, config).run()

    # we add it to the peers list for later beacon nodes to connect
    peer = retry(beacon.get_peer)
    if peer:
        config.peers.append(peer)
    else:
        print("Could not get peer")
        return []

    return list(filter(None, [geth_proc, beacon_proc, validator_proc]))


def send_interrupt(*procs: tuple[list[subprocess.Popen]]):
    for proc in itertools.chain.from_iterable(procs):
        if proc is None:
            continue
        os.kill(proc.pid, signal.SIGINT)


if __name__ == '__main__':
    os.system(f"killall validator geth beacon-chain")
    config = NodeConfigBuilder().build()
    if config.devnet_path.exists():
        retry(os.system, f"rm -r {config.devnet_path}")

    setup()
    setup_node(1)
    setup_node(2)

    clients = start_node(1)
    # wait 6x12 seconds to join
    WAIT_SECONDS = 80
    sleep(WAIT_SECONDS)
    clients2 = start_node(2)
    # clients2 = []

    if not config.create_new_terminal and False:
        from terminals import run_in_curses
        run_in_curses([['tail', '-f', str(config.node_path[1] / 'geth.log')]],
                      [['tail', '-f', str(config.node_path[1] / 'beacon.log')]],
                      [['tail', '-f', str(config.node_path[1] / 'validator.log')]],
                      # [['tail', '-f', str(config.node_path[2] / 'geth.log')],
                      # ['tail', '-f', str(config.node_path[2] / 'beacon.log')]]
                      )
    else:
        input("Press enter to continue...")

    check_error(clients, clients2)
