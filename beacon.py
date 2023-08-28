import re
import json
import subprocess
from node_config import NodeConfig
import port_assignment

FIRST_NODE = 0

class BeaconNode:
    def __init__(self, no, config: NodeConfig) -> None:
        self.no = no
        self.node_path = config.node_path[no]
        self.devnet_path = config.devnet_path
        self.geth_path = config.geth_path[no]
        self.peers = config.peers
        self.address = config.addresses[no]
        self.log_path = self.node_path / 'beacon.log'
        self.create_new_terminal = config.create_new_terminal

    def get_args(self) -> list[str]:
        raise NotImplementedError

    def get_peer(self) -> str | None:
        raise NotImplementedError
    
    def set_log_path(self, log_path: str):
        self.log_path = log_path
        return self
    
    def run(self) -> subprocess.Popen:
        beacon_cmd : list[str] = self.get_args()

        beacon_log = open(self.log_path, 'w')
        print('Starting beacon node', self.no, ':', ' '.join(beacon_cmd))
        if not self.create_new_terminal:
            beacon_proc = subprocess.Popen(
                beacon_cmd, stdout=beacon_log, stderr=beacon_log, text=True)
        else:
            beacon_proc = subprocess.Popen(
                ['xfce4-terminal', '-e', ' '.join(beacon_cmd)])
        
        return beacon_proc


class PrysmNode(BeaconNode):
    def get_args(self):
        port_assignment.beacon_peer_arguments = [f'--peer={peer}' for peer in self.peers]
        return [
            'beacon-chain',
            f"--datadir={self.node_path / 'beacondata'}",
            # 0 for first node, 1 for second node
            f'--min-sync-peers={self.no}',
            f"--genesis-state={self.devnet_path / 'genesis.ssz'}",
            "--interop-eth1data-votes",
            '--bootstrap-node=',
            f'--chain-config-file={self.devnet_path / "config.yml"}',
            '--chain-id=32382',
            '--rpc-host=127.0.0.1',
            f'--rpc-port={port_assignment.beacon_port(self.no)}',
            '--grpc-gateway-host=127.0.0.1',
            '--p2p-local-ip=127.0.0.1',
            f'--grpc-gateway-port={port_assignment.beacon_grpc_port(self.no)}',
            f'--p2p-tcp-port={port_assignment.beacon_p2p_tcp_port(self.no)}',
            f'--p2p-udp-port={port_assignment.beacon_p2p_udp_port(self.no)}',
            f'--p2p-static-id',
            f'--execution-endpoint=http://localhost:{port_assignment.geth_authrpc_port(FIRST_NODE)}',
            '--accept-terms-of-use',
            f'--jwt-secret={self.node_path / "jwt.hex"}',

            f'--suggested-fee-recipient=0x{self.address}',
            *port_assignment.beacon_peer_arguments]

    def get_peer(self):
        peer_result = subprocess.run(
            ['curl', f'localhost:{port_assignment.beacon_monitoring_port(self.no)}/p2p'], capture_output=True, text=True).stdout.strip()
        # example peer:
        # bootnode=[]
        # self=/ip4/172.17.195.116/tcp/13000/p2p/16Uiu2HAkzFu54hZr8ZB4mn9ZiKwc52bARDJdJMtnqbUDf5fMNmWk
        # extract '/ip4/...' part
        pattern = r"/ip4/[a-zA-Z0-9/\.]+"
        match = re.search(pattern, peer_result)

        if match:
            ip4_part = match.group()
            return ip4_part


class TekuNode(BeaconNode):
    def get_args(self):
        # return teku starting arguments
        return [
            'teku',
            '--network=minimal',
            f'--data-path={self.node_path / "teku"}',
            f'--data-beacon-path={self.node_path / "beacondata"}',
            '--data-storage-mode=prune',
            f'--ee-endpoint=http://localhost:{port_assignment.geth_authrpc_port(FIRST_NODE)}',
            f'--ee-jwt-secret-file={self.node_path / "jwt.hex"}',
            f'--p2p-peer-lower-bound={self.no}',
            f'--initial-state={self.devnet_path / "genesis.ssz"}',
            f'--p2p-discovery-bootnodes=',
            f'--p2p-enabled=true',
            f'--p2p-interface=127.0.0.1',
            f'--p2p-port={port_assignment.beacon_p2p_tcp_port(self.no)}',
            f'--p2p-udp-port={port_assignment.beacon_p2p_udp_port(self.no)}',
            f'--p2p-discovery-enabled=false',
            f'--p2p-static-peers={",".join(self.peers)}',
            '--rest-api-enabled=true',
            '--rest-api-interface=127.0.0.1',
            f'--rest-api-port={port_assignment.beacon_monitoring_port(self.no)}',        ]

    def get_peer(self):
        peer_result = subprocess.run(
            ['curl', f'localhost:{port_assignment.beacon_monitoring_port(self.no)}/eth/v1/node/identity'], capture_output=True, text=True).stdout.strip()
        # parse the JSON response and extract the address
        peer_json = json.loads(peer_result)
        try:
            return peer_json['data']['p2p_addresses'][0]
        except ValueError:
            return None
