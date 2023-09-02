
# environment
import json
import os
import sys
from pathlib import Path

class NodeConfigBuilder:
    def __init__(self):
        self.num_nodes = 3
        self.db_engine = 'pebble'
        self.devnet_path = Path('/dev/shm/devnet')
        self.config_suffix = ''
        self.reset = True
        
        project_root = Path(__file__).parent
        self.key_dir = (project_root / Path('keys-posdevnet')).absolute()
        self.contract_path = (project_root / Path('contract')).absolute()
        self.config_path = (project_root / Path('config')).absolute()

    def with_num_nodes(self, num_nodes):
        self.num_nodes = num_nodes
        return self

    def with_db_engine(self, db_engine):
        self.db_engine = db_engine
        return self

    def with_config_suffix(self, config_suffix):
        self.config_suffix = config_suffix
        return self

    def with_key_dir(self, key_dir):
        self.key_dir = key_dir
        return self
    
    def with_devnet_path(self, devnet_path):
        self.devnet_path = Path(devnet_path).absolute()
        return self

    def with_contract_path(self, contract_path):
        self.contract_path = Path(contract_path).absolute()
        return self
    
    def with_config_path(self, config_path):
        self.config_path = Path(config_path).absolute()
        return self
    
    def with_reset(self, reset):
        self.reset = reset
        return self

    def build(self):
        config_yml = None
        with open(self.config_path / f'prysm{self.config_suffix}.yml', 'r') as f:
            config_yml = f.read()

        genesis_json = None
        with open(self.config_path / f'genesis{self.config_suffix}.json', 'r') as f:
            genesis_json = f.read()

        node_path = {}
        geth_path = {}
        for i in range(0, self.num_nodes):
            node_path[i] = Path(self.devnet_path) / f'node{i}'
            geth_path[i] = node_path[i] / 'geth'

        peers = []
        geth_peers = []
        addresses = []
        for i in range(0, self.num_nodes):
            with open(self.key_dir / f'key{i}.json', 'r') as f:
                addresses.append(json.load(f)['address'])

        return NodeConfig(self.num_nodes, self.db_engine, self.devnet_path, self.config_suffix, config_yml, genesis_json, node_path, geth_path, self.key_dir, peers, geth_peers, addresses, self.contract_path, self.reset)


class NodeConfig:
    def __init__(self, num_nodes, db_engine, devnet_path, config_suffix, config_yml, genesis_json, node_path, geth_path, key_dir, peers, geth_peers, addresses, contract_path, reset):
        self.num_nodes : int = num_nodes
        self.db_engine : str = db_engine
        self.devnet_path : Path = devnet_path
        self.config_suffix : str = config_suffix
        self.config_yml : str = config_yml
        self.genesis_json : str = genesis_json
        self.node_path : list[Path] = node_path
        self.geth_path : list[Path] = geth_path
        self.key_dir : Path = key_dir
        self.peers : list[str] = peers
        self.geth_peers : list[str] = geth_peers
        self.addresses : list[str] = addresses
        self.contract_path : Path = contract_path
        self.reset : bool = reset

        self.create_new_terminal : bool = False
    
    @property
    def contract_address_path(self):
        return self.devnet_path / 'contract_address'
    
    @property
    def contract_address(self):
        try:
            return self.contract_address_path.read_text()
        except Exception as e:
            print("Failed to read contract address file", file=sys.stderr)
            raise e
    
    def set_contract_address(self, address):
        self.contract_address_path.write_text(address)
            