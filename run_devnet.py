#!/usr/bin/env python3

import itertools
import os
import re
import shutil
import subprocess
import signal
from time import sleep
from typing import Callable, TypeVar

from web3 import Web3, IPCProvider
from beacon import BeaconNode, PrysmNode, TekuNode
from env import DEVNET_PATH, CONFIG_YML, GENESIS_JSON, NODE_PATH, GETH_PATH, KEY_DIR, ADDRESSES, PEERS, GETH_PEERS, DB_ENGINE, TERMINAL

from env import beacon_port, beacon_grpc_port, beacon_p2p_tcp_port, beacon_p2p_udp_port, geth_peer_port, geth_http_port, geth_ws_port, geth_authrpc_port, validator_grpc_port, validator_rpc_port


def setup():
    DEVNET_PATH.mkdir(exist_ok=True)
    os.chdir(DEVNET_PATH)

    with open('config.yml', 'w') as f:
        f.write(CONFIG_YML)

    with open('genesis.json', 'w') as f:
        f.write(GENESIS_JSON)


def setup_node(no=1):
    node_path = NODE_PATH[no]
    geth_path = GETH_PATH[no]

    node_path.mkdir(exist_ok=True)

    print(f"Initializing node {no}...")

    # Before starting the beacon node, we need to generate the genesis state for it
    if not (DEVNET_PATH / 'genesis.ssz').exists():
        print('Generating genesis state for node', no, '...')
        prysmctl_cmd = [
            'prysmctl',
            'testnet',
            'generate-genesis',
            '--fork=bellatrix',
            '--num-validators=64',
            f'--output-ssz={DEVNET_PATH / "genesis.ssz"}',
            f'--chain-config-file={DEVNET_PATH / "config.yml"}',
            f'--geth-genesis-json-in={DEVNET_PATH / "genesis.json"}',
            f'--geth-genesis-json-out={DEVNET_PATH / "genesis.json"}',
        ]

        retry(lambda: subprocess.run(prysmctl_cmd).returncode == 0)
        # print current unix timestamp
        # print('Current unix timestamp:', int(time.time()))

    subprocess.run(['geth', '--datadir=' + str(geth_path), f'--db.engine={DB_ENGINE}',
                   'init', str(DEVNET_PATH / 'genesis.json')], capture_output=True, text=True)

    # copy key to the geth directory
    shutil.copy(KEY_DIR / f'key{no}.json', geth_path / 'keystore' / 'key.json')

    with open(node_path / "jwt.hex", 'w') as f:
        f.write(subprocess.run(['openssl', 'rand', '-hex', '32'],
                capture_output=True, text=True).stdout.strip())


T = TypeVar('T')

def retry(func: Callable[..., T | None], *args, **kwargs) -> T | None:
    for delay in [1, 2, 4]:
        try:
            result = func(*args, **kwargs)
            if result:
                return result
        except Exception as e:
            print(e)
        sleep(delay)
    return func(*args, **kwargs)


def check_error(*procs: list[subprocess.Popen | None]) -> int:
    error_value = 0
    for ind, proc_group in enumerate(procs):
        for proc in proc_group:
            if proc is None:
                continue
            name = f'Node {ind} {proc.args[0]}'
            if proc.returncode != 0:
                if proc.poll() is None:
                    print(f"{name} running...")
                else:
                    print(f"{name} ended with error")
                    error_value = proc.returncode
            else:
                print(f"{name} ended successfully")
    return error_value


def start_node(no=1) -> list[subprocess.Popen]:
    """Starts a node with the given number
    Returns the processes for geth, beacon and validator"""
    node_path = NODE_PATH[no]
    geth_path = GETH_PATH[no]

    geth_cmd = [
        'geth',
        '--http',
        '--http.api=eth,engine',
        f'--datadir={geth_path}',
        '--allow-insecure-unlock',
        f'--unlock=0x{ADDRESSES[no - 1]}',
        '--password=/dev/null',
        '--nodiscover',
        '--syncmode=full',
        f'--authrpc.jwtsecret={node_path / "jwt.hex"}',
        f'--port={geth_peer_port(no)}',
        f'--http.port={geth_http_port(no)}',
        f'--ws.port={geth_ws_port(no)}',
        f'--authrpc.port={geth_authrpc_port(no)}',
        '--mine',
        f'--miner.etherbase={ADDRESSES[no - 1]}',
    ]

    print('Starting Geth for node', no, ':', ' '.join(geth_cmd))
    geth_log = open(node_path / 'geth.log', 'w')
    if not TERMINAL:
        geth_proc = subprocess.Popen(
            geth_cmd, stdout=geth_log, stderr=geth_log, text=True)
    else:
        geth_proc = subprocess.Popen(
            ['xfce4-terminal', '-e', ' '.join(geth_cmd)])

    # Add geth node to peers list and connect it to existing nodes
    ipc_path = geth_path / 'geth.ipc'
    retry(lambda: ipc_path.exists())
    node = Web3(IPCProvider(str(ipc_path)))
    for peer in GETH_PEERS:
        if node.geth.admin.add_peer(peer):
            print('Successfully added peer', peer)
        else:
            print('Failed to connect to peer', peer)
    enodeUrl = node.geth.admin.node_info()['enode']
    GETH_PEERS.append(enodeUrl)

    # start beacon node
    beacon : BeaconNode = TekuNode(no)
    
    beacon_cmd : list[str] = beacon.get_args()

    beacon_log = open(node_path / 'beacon.log', 'w')
    print('Starting beacon node', no, ':', ' '.join(beacon_cmd))
    if not TERMINAL:
        beacon_proc = subprocess.Popen(
            beacon_cmd, stdout=beacon_log, stderr=beacon_log, text=True)
    else:
        beacon_proc = subprocess.Popen(
            ['xfce4-terminal', '-e', ' '.join(beacon_cmd)])
    
    # check if beacon node is running
    sleep(3)
    if check_error([beacon_proc]) != 0:
        print("Beacon node not running")
        with open(node_path / 'beacon.log', 'r') as f:
            print(f.read())
        return []

    validator_proc = None

    if no == 1:
        validator_cmd = [
            'validator',
            f'--beacon-rpc-provider=127.0.0.1:{beacon_port(no)}',
            f'--datadir={node_path / "validatordata"}',
            '--accept-terms-of-use',
            '--interop-num-validators=64',
            '--interop-start-index=0',
            f'--chain-config-file={DEVNET_PATH / "config.yml"}',
            f'--grpc-gateway-port={validator_grpc_port(no)}',
            f'--rpc-port={validator_rpc_port(no)}',
        ]

        validator_log = open(node_path / 'validator.log', 'w')
        print('Starting validator node', no, ':', ' '.join(validator_cmd))
        if TERMINAL:
            validator_proc = subprocess.Popen(
                ['xfce4-terminal', '-e', ' '.join(validator_cmd)])
        else:
            validator_proc = subprocess.Popen(
                validator_cmd, stdout=validator_log, stderr=validator_log, text=True)

    # we add it to the peers list for later beacon nodes to connect
    peer = retry(beacon.get_peer)
    if peer:
        PEERS.append(peer)
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
    if DEVNET_PATH.exists():
        retry(os.system, f"rm -r {DEVNET_PATH}")

    setup()
    setup_node(1)
    setup_node(2)

    clients = start_node(1)
    # wait 6x12 seconds to join
    WAIT_SECONDS = 80
    sleep(WAIT_SECONDS)
    clients2 = start_node(2)
    # clients2 = []

    if not TERMINAL and False:
        from terminals import run_in_curses
        run_in_curses([['tail', '-f', str(NODE_PATH[1] / 'geth.log')]],
                      [['tail', '-f', str(NODE_PATH[1] / 'beacon.log')]],
                      [['tail', '-f', str(NODE_PATH[1] / 'validator.log')]],
                      # [['tail', '-f', str(NODE_PATH[2] / 'geth.log')],
                      # ['tail', '-f', str(NODE_PATH[2] / 'beacon.log')]]
                      )
    else:
        input("Press enter to continue...")

    check_error(clients, clients2)
