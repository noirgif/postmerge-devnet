#!/usr/bin/env python3

import itertools
import json
import os
import re
import shutil
import subprocess
import signal
from pathlib import Path
from time import sleep

from web3 import Web3, IPCProvider

# environment
TERMINAL = False

os.chdir(Path(__file__).parent)

# config
NUM_NODES = 3
# which db for geth to use, leveldb(default) or pebble(new)
DB_ENGINE = 'pebble'

# paths
DEVNET_PATH = Path('/dev/shm/devnet')
if 'DEVNET_PATH' in os.environ:
    DEVNET_PATH = Path(os.environ['DEVNET_PATH']).absolute()

# decides which set of config files to use, -orig is the one from eth-pos-devnet
CONFIG_SUFFIX = ''

CONFIG_YML = None
with open(f'config/prysm{CONFIG_SUFFIX}.yml', 'r') as f:
    CONFIG_YML = f.read()

GENESIS_JSON = None
with open(f'config/genesis{CONFIG_SUFFIX}.json', 'r') as f:
    GENESIS_JSON = f.read()

NODE_PATH: dict[int, Path] = {}
GETH_PATH: dict[int, Path] = {}
for i in range(1, NUM_NODES + 1):
    NODE_PATH[i] = DEVNET_PATH / f'node{i}'
    GETH_PATH[i] = NODE_PATH[i] / 'geth'

# path to secret keys
KEY_DIR = Path('keys-posdevnet').absolute()


# node configurations
# beacon and geth peer addresses
PEERS: list[str] = []
GETH_PEERS: list[str] = []
# read wallet addresses from keys
ADDRESSES = []
for i in range(1, NUM_NODES + 1):
    with open(Path('keys-posdevnet') / f'key{i}.json', 'r') as f:
        ADDRESSES.append(json.load(f)['address'])


# ports
def new_port_assignment(base, step):
    # assign new ports to each node to avoid conflicts
    def port(no=1):
        return base + (no - 1) * step
    return port


geth_http_port = new_port_assignment(8545, 15)
geth_ws_port = new_port_assignment(8546, 15)
geth_authrpc_port = new_port_assignment(8551, 15)
geth_peer_port = new_port_assignment(30303, 1)
beacon_port = new_port_assignment(4000, 1)
beacon_grpc_port = new_port_assignment(3500, 1)
beacon_p2p_udp_port = new_port_assignment(12000, 1)
beacon_p2p_tcp_port = new_port_assignment(13000, 1)
beacon_monitoring_port = new_port_assignment(8000, 1)
validator_grpc_port = new_port_assignment(7500, 1)
validator_rpc_port = new_port_assignment(7000, 1)


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


def retry(func, *args, **kwargs):
    for delay in [1, 2, 4]:
        try:
            result = func(*args, **kwargs)
            if result:
                return result
        except Exception as e:
            print(e)
        sleep(delay)
    return func(*args, **kwargs)


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
    beacon_peer_arguments = [f'--peer={peer}' for peer in PEERS]
    beacon_cmd = [
        'beacon-chain',
        f"--datadir={node_path / 'beacondata'}",
        # 0 for first node, 1 for second node
        f'--min-sync-peers={no-1}',
        f"--genesis-state={DEVNET_PATH / 'genesis.ssz'}",
        "--interop-eth1data-votes",
        '--bootstrap-node=',
        f'--chain-config-file={DEVNET_PATH / "config.yml"}',
        '--chain-id=32382',
        '--rpc-host=127.0.0.1',
        f'--rpc-port={beacon_port(no)}',
        '--grpc-gateway-host=127.0.0.1',
        '--p2p-local-ip=127.0.0.1',
        f'--grpc-gateway-port={beacon_grpc_port(no)}',
        f'--p2p-tcp-port={beacon_p2p_tcp_port(no)}',
        f'--p2p-udp-port={beacon_p2p_udp_port(no)}',
        f'--p2p-static-id',
        f'--execution-endpoint=http://localhost:{geth_authrpc_port(1)}',
        '--accept-terms-of-use',
        f'--jwt-secret={NODE_PATH[1] / "jwt.hex"}',

        f'--suggested-fee-recipient=0x{ADDRESSES[no - 1]}',
        *beacon_peer_arguments]

    beacon_log = open(node_path / 'beacon.log', 'w')
    print('Starting beacon node', no, ':', ' '.join(beacon_cmd))
    if not TERMINAL:
        beacon_proc = subprocess.Popen(
            beacon_cmd, stdout=beacon_log, stderr=beacon_log, text=True)
    else:
        beacon_proc = subprocess.Popen(
            ['xfce4-terminal', '-e', ' '.join(beacon_cmd)])

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
    def get_peer():
        peer_result = subprocess.run(
            ['curl', 'localhost:8080/p2p'], capture_output=True, text=True).stdout.strip()
        # example peer:
        # bootnode=[]
        # self=/ip4/172.17.195.116/tcp/13000/p2p/16Uiu2HAkzFu54hZr8ZB4mn9ZiKwc52bARDJdJMtnqbUDf5fMNmWk
        # extract '/ip4/...' part
        pattern = r"/ip4/[a-zA-Z0-9/\.]+"
        match = re.search(pattern, peer_result)

        if match:
            ip4_part = match.group()
            return ip4_part

    peer = retry(get_peer)
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


def check_error(*procs: list[subprocess.Popen | None]):
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
            else:
                print(f"{name} ended successfully")


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
