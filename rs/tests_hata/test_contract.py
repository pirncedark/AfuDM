from pathlib import Path
import unittest
R = Path(__file__).resolve().parents[1]
class FeatureContract(unittest.TestCase):
    def test_feature_opt_in(self):
        s = (R/'app/Cargo.toml').read_text()
        self.assertIn('test-kapisi = []', s)
    def test_module_gated(self):
        s = (R/'app/src/main.rs').read_text()
        self.assertIn('#[cfg(feature = "test-kapisi")]\nmod test_kapisi;', s)
    def test_auth_and_loopback(self):
        s = (R/'app/src/test_kapisi.rs').read_text()
        self.assertIn('127.0.0.1', s)
        self.assertIn('UNAUTHORIZED', s)
        self.assertIn('bridge::api_call', s)
if __name__ == '__main__': unittest.main()
