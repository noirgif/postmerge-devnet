from node_config import NodeConfig
import port_assignment
import subprocess

class EthExecutor:
    def __init__(self, no, config: NodeConfig):
        self.no = no
        self.address = config.addresses[no]
        self.node_path = config.node_path[no]
        self.geth_path = config.geth_path[no]
        self.log_path = self.node_path / 'geth.log'
    
    def set_log_path(self, log_path: str):
        self.log_path = log_path
        return self
    
    def set_node_path(self, node_path: str):
        self.node_path = node_path
        self.log_path = self.node_path / 'geth.log'
        return self
    
    def set_geth_path(self, geth_path: str):
        self.geth_path = geth_path
        return self

    def run():
        raise NotImplementedError


class GethNode(EthExecutor):

    def run(self):
        geth_cmd = [
            'geth',
            '--http',
            '--http.api=eth,engine',
            f'--datadir={self.geth_path}',
            '--allow-insecure-unlock',
            f'--unlock=0x{self.address}',
            '--password=/dev/null',
            '--nodiscover',
            '--syncmode=full',
            f'--authrpc.jwtsecret={self.node_path / "jwt.hex"}',
            f'--port={port_assignment.geth_peer_port(self.no)}',
            f'--http.port={port_assignment.geth_http_port(self.no)}',
            f'--ws.port={port_assignment.geth_ws_port(self.no)}',
            f'--authrpc.port={port_assignment.geth_authrpc_port(self.no)}',
            '--mine',
            f'--miner.etherbase={self.address}',
        ]

        print('Starting Geth for node', self.no, ':', ' '.join(geth_cmd))
        with open(self.log_path, 'w') as geth_log:
            if not self.create_new_terminal:
                return subprocess.Popen(
                    geth_cmd, stdout=geth_log, stderr=geth_log, text=True)
            else:
                return subprocess.Popen(
                    ['xfce4-terminal', '-e', ' '.join(geth_cmd)])