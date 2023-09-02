import unittest
from node_config import NodeConfigBuilder
from unittest.mock import mock_open, patch

class TestNodeConfigBuilder(unittest.TestCase):
    @patch('builtins.open', mock_open())
    def test_build(self):
        open_mock = open  # This grabs the patched open
        node_config_builder = NodeConfigBuilder()
        side_effect = [
            mock_open(read_data="prysm config").return_value,
            mock_open(read_data="genesis").return_value,]
        
        keys = []
        for i in range(0, node_config_builder.num_nodes):
            keys.append("key" + str(i))
            side_effect.append(mock_open(read_data='{"address": "%s"}' % keys[i]).return_value)
        
        open_mock.side_effect = side_effect

        node_config = node_config_builder.build()
        self.assertEqual(node_config.config_yml, "prysm config")
        self.assertEqual(node_config.genesis_json, "genesis")
        self.assertEqual(node_config.addresses, keys)

if __name__ == "__main__":
    unittest.main()