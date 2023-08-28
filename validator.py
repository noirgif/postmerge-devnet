from node_config import NodeConfig
import port_assignment
import subprocess

class Validator:
    def __init__(self, no: int, node_config: NodeConfig):
        self.no = no
        self.node_path = node_config.node_path[no]
        self.devnet_path = node_config.devnet_path
        self.geth_path = node_config.geth_path[no]
        self.peers = node_config.peers
        self.address = node_config.addresses[no]
        self.log_path = self.node_path / 'validator.log'
        self.create_new_terminal = node_config.create_new_terminal
    
    def set_log_path(self, log_path: str):
        self.log_path = log_path
        return self
    
    def set_node_path(self, node_path: str):
        self.node_path = node_path
        self.log_path = self.node_path / 'validator.log'
        return self
    
    def set_geth_path(self, geth_path: str):
        self.geth_path = geth_path
        return self
    

class PrysmValidator(Validator):
    def run(self) -> subprocess.Popen:
        validator_cmd = [
            'validator',
            f'--beacon-rpc-provider=127.0.0.1:{port_assignment.beacon_port(self.no)}',
            f'--datadir={self.node_path / "validatordata"}',
            '--accept-terms-of-use',
            '--interop-num-validators=64',
            '--interop-start-index=0',
            f'--chain-config-file={self.devnet_path / "config.yml"}',
            f'--grpc-gateway-port={port_assignment.validator_grpc_port(self.no)}',
            f'--rpc-port={port_assignment.validator_rpc_port(self.no)}',
        ]

        with open(self.log_path, 'w') as validator_log:
            print('Starting validator node', self.no, ':', ' '.join(validator_cmd))
            if self.create_new_terminal:
                return subprocess.Popen(
                    ['xfce4-terminal', '-e', ' '.join(validator_cmd)])
            else:
                return subprocess.Popen(
                    validator_cmd, stdout=validator_log, stderr=validator_log, text=True)
        