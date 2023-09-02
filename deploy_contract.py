from web3 import Web3
from pathlib import Path
import json
from node_config import NodeConfig
import port_assignment

def setup_contract(config: NodeConfig):
    # Connect to a local Ethereum node
    w3 = Web3(Web3.HTTPProvider(f'http://localhost:{port_assignment.geth_http_port(0)}'))


    # Ensure you're connected to Ethereum
    assert w3.isConnected()

    # Replace these with your contract ABI and bytecode from the Remix IDE
    ABI = json.load(Path(config.contract_path / "abi").read_text())
    BYTECODE = Path(config.contract_path / "bytecode").read_text()

    # Deploy the contract
    contract = w3.eth.contract(abi=ABI, bytecode=BYTECODE)
    tx_hash = contract.constructor().transact({'from': w3.eth.accounts[0]})
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)

    # Store the contract address to a file
    contract_address = tx_receipt['contractAddress']
    config.set_contract_address(contract_address)

    deployed_contract = w3.eth.contract(address=contract_address, abi=ABI)

    # Store a value
    tx_hash = deployed_contract.functions.store(42).transact({'from': w3.eth.accounts[0]})
    w3.eth.waitForTransactionReceipt(tx_hash)

    # Retrieve the stored value
    result = deployed_contract.functions.retrieve().call()
    print(f"Stored value: {result}")
