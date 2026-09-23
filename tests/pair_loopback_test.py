import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.server import _loopback_istemci


class PairLoopbackTest(unittest.TestCase):
    def test_only_loopback_addresses_can_receive_pair_token(self):
        self.assertTrue(_loopback_istemci(("127.0.0.1", 1234)))
        self.assertTrue(_loopback_istemci(("::1", 1234)))
        self.assertFalse(_loopback_istemci(("192.168.1.25", 1234)))
        self.assertFalse(_loopback_istemci(("not-an-ip", 1234)))


if __name__ == "__main__":
    unittest.main()
