
# environment
import json
import os
from pathlib import Path


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