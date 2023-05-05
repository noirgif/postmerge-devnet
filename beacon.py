import re
import subprocess
from env import *


class BeaconNode:
    def __init__(self, no) -> None:
        self.no = no

    def get_args(self) -> list[str]:
        raise NotImplementedError

    def get_peer(self) -> str | None:
        raise NotImplementedError


class PrysmNode(BeaconNode):
    def get_args(self):
        node_path = NODE_PATH[self.no]
        beacon_peer_arguments = [f'--peer={peer}' for peer in PEERS]
        return [
            'beacon-chain',
            f"--datadir={node_path / 'beacondata'}",
            # 0 for first node, 1 for second node
            f'--min-sync-peers={self.no-1}',
            f"--genesis-state={DEVNET_PATH / 'genesis.ssz'}",
            "--interop-eth1data-votes",
            '--bootstrap-node=',
            f'--chain-config-file={DEVNET_PATH / "config.yml"}',
            '--chain-id=32382',
            '--rpc-host=127.0.0.1',
            f'--rpc-port={beacon_port(self.no)}',
            '--grpc-gateway-host=127.0.0.1',
            '--p2p-local-ip=127.0.0.1',
            f'--grpc-gateway-port={beacon_grpc_port(self.no)}',
            f'--p2p-tcp-port={beacon_p2p_tcp_port(self.no)}',
            f'--p2p-udp-port={beacon_p2p_udp_port(self.no)}',
            f'--p2p-static-id',
            f'--execution-endpoint=http://localhost:{geth_authrpc_port(1)}',
            '--accept-terms-of-use',
            f'--jwt-secret={NODE_PATH[1] / "jwt.hex"}',

            f'--suggested-fee-recipient=0x{ADDRESSES[self.no - 1]}',
            *beacon_peer_arguments]

    def get_peer(self):
        peer_result = subprocess.run(
            ['curl', f'localhost:{beacon_monitoring_port(self.no)}/p2p'], capture_output=True, text=True).stdout.strip()
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
        node_path = NODE_PATH[self.no]
        return [
            'teku',
            '--network=minimal',
            f'--data-path={node_path / "teku"}',
            f'--data-beacon-path={node_path / "beacondata"}',
            '--data-storage-mode=prune',
            f'--ee-endpoint=http://localhost:{geth_authrpc_port(1)}',
            f'--ee-jwt-secret-file={NODE_PATH[1] / "jwt.hex"}',
            f'--p2p-peer-lower-bound={self.no-1}',
            f'--initial-state={DEVNET_PATH / "genesis.ssz"}',
            f'--p2p-discovery-bootnodes=',
            f'--p2p-enabled=true',
            f'--p2p-interface=127.0.0.1',
            f'--p2p-port={beacon_p2p_tcp_port(self.no)}',
            f'--p2p-udp-port={beacon_p2p_udp_port(self.no)}',
            f'--p2p-discovery-enabled=false',
            f'--p2p-static-peers={",".join(PEERS)}',
            '--rest-api-enabled=true',
            '--rest-api-interface=127.0.0.1',
            f'--rest-api-port={beacon_monitoring_port(self.no)}',
        ]

    def get_peer(self):
        peer_result = subprocess.run(
            ['curl', f'localhost:{beacon_monitoring_port(self.no)}/eth/v1/node/identity'], capture_output=True, text=True).stdout.strip()
        # parse the JSON response and extract the address
        peer_json = json.loads(peer_result)
        try:
            return peer_json['data']['p2p_addresses'][0]
        except ValueError:
            return None
