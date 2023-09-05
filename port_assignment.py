# ports
def new_port_assignment(base, step):
    # assign new ports to each node to avoid conflicts
    def port(no):
        return base + no * step
    return port


geth_http_port = new_port_assignment(8545, 15)
geth_ws_port = new_port_assignment(8546, 15)
geth_authrpc_port = new_port_assignment(8551, 15)
geth_peer_port = new_port_assignment(30303, 1)
beacon_port = new_port_assignment(4000, 1)
beacon_grpc_port = new_port_assignment(3500, 1)
beacon_p2p_udp_port = new_port_assignment(12000, 1)
beacon_p2p_tcp_port = new_port_assignment(13000, 1)
beacon_monitoring_port = new_port_assignment(8080, 1)
validator_grpc_port = new_port_assignment(7500, 1)
validator_rpc_port = new_port_assignment(7000, 1)