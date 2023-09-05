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


def setup_node(no, config: NodeConfig):
    """
    Sets up a node by creating the necessary directories and configuration files.

    Args:
        no (int): The node number to set up.
        config (NodeConfig): The configuration object for the devnet.

    Returns:
        None
    """
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
            '--fork=capella',
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


def setup(config: NodeConfig):
    """
    Sets up the devnet by creating the necessary directories and configuration files and setup each node

    Args:
        config (NodeConfig): The configuration object for the devnet.

    Returns:
        None
    """
    if config.reset:
        if config.devnet_path.exists():
            retry(os.system, f"rm -r {config.devnet_path}")

    config.devnet_path.mkdir(exist_ok=True)
    os.chdir(config.devnet_path)

    with open('config.yml', 'w') as f:
        f.write(config.config_yml)

    with open('genesis.json', 'w') as f:
        f.write(config.genesis_json)
    
    for no in range(config.num_nodes):
        setup_node(no, config)


def start_node(no, config: NodeConfig) -> list[subprocess.Popen]:
    """
    Starts a node with the given number and returns the processes for geth, beacon and validator.

    Args:
        no (int): The node number to start.
        config (NodeConfig): The configuration object for the devnet.

    Returns:
        A list of subprocess.Popen objects for the geth, beacon and validator processes.
    """
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
    beacon : BeaconNode = PrysmNode(no, config)
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
        print("[Error] Could not get p2p address of the node")
        return []

    return list(filter(None, [geth_proc, beacon_proc, validator_proc]))


def send_interrupt(*procs: tuple[list[subprocess.Popen]]):
    """
    Sends a SIGINT signal to the specified processes.

    Args:
        *procs: A variable number of tuples, where each tuple contains a list of subprocess.Popen objects.

    Returns:
        None
    """
    for proc in itertools.chain.from_iterable(procs):
        if proc is None:
            continue
        os.kill(proc.pid, signal.SIGINT)


def main():
    import argparse
    parser = argparse.ArgumentParser(
                    prog='run_devnet.py',
                    description='Run a 2-node devnet for testing purposes',
    )
    parser.add_argument('-n', '--num-nodes', type=int, default=2,)

    args = parser.parse_args()

    os.system(f"killall validator geth beacon-chain")
    config = NodeConfigBuilder().with_num_nodes(args.num_nodes).build()

    setup(config)

    clients = []
    for no in range(config.num_nodes):
        if no != 0:
            # wait 6x12 seconds to join
            WAIT_SECONDS = 80
            sleep(WAIT_SECONDS)
        clients.append(start_node(no, config))

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

    check_error(*clients)

if __name__ == '__main__':
    main()