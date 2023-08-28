
# environment
import json
import os
from pathlib import Path

import os
import json
from pathlib import Path

class NodeConfigBuilder:
    def __init__(self):
        self.num_nodes = 3
        self.db_engine = 'pebble'
        self.devnet_path = '/dev/shm/devnet'
        self.config_suffix = ''
        self.key_dir = 'keys-posdevnet'

    def with_num_nodes(self, num_nodes):
        self.num_nodes = num_nodes
        return self

    def with_db_engine(self, db_engine):
        self.db_engine = db_engine
        return self

    def with_devnet_path(self, devnet_path):
        self.devnet_path = devnet_path
        return self

    def with_config_suffix(self, config_suffix):
        self.config_suffix = config_suffix
        return self

    def with_key_dir(self, key_dir):
        self.key_dir = key_dir
        return self

    def build(self):
        os.chdir(Path(__file__).parent)

        config_yml = None
        with open(f'config/prysm{self.config_suffix}.yml', 'r') as f:
            config_yml = f.read()

        genesis_json = None
        with open(f'config/genesis{self.config_suffix}.json', 'r') as f:
            genesis_json = f.read()

        node_path = {}
        geth_path = {}
        for i in range(1, self.num_nodes + 1):
            node_path[i] = Path(self.devnet_path) / f'node{i}'
            geth_path[i] = node_path[i] / 'geth'

        key_dir = Path(self.key_dir).absolute()

        peers = []
        geth_peers = []
        addresses = []
        for i in range(1, self.num_nodes + 1):
            with open(Path(self.key_dir) / f'key{i}.json', 'r') as f:
                addresses.append(json.load(f)['address'])

        return NodeConfig(self.num_nodes, self.db_engine, Path(self.devnet_path).absolute(), self.config_suffix, config_yml, genesis_json, node_path, geth_path, key_dir, peers, geth_peers, addresses)


class NodeConfig:
    def __init__(self, num_nodes, db_engine, devnet_path, config_suffix, config_yml, genesis_json, node_path, geth_path, key_dir, peers, geth_peers, addresses):
        self.num_nodes = num_nodes
        self.db_engine = db_engine
        self.devnet_path = devnet_path
        self.config_suffix = config_suffix
        self.config_yml = config_yml
        self.genesis_json = genesis_json
        self.node_path = node_path
        self.geth_path = geth_path
        self.key_dir = key_dir
        self.peers = peers
        self.geth_peers = geth_peers
        self.addresses = addresses
        self.create_new_terminal = False