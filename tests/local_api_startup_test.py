"""Local API must serve requests without depending on reverse DNS."""
from pathlib import Path
import http.client
import socket
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.server import LocalAPI


class LocalAPIStartupTest(unittest.TestCase):
    def test_api_answers_while_reverse_dns_is_unavailable(self):
        for lan in (False, True):
            with self.subTest(lan=lan):
                release_dns = threading.Event()
                started = threading.Event()
                errors = []
                api = LocalAPI.__new__(LocalAPI)
                api.lan = lan
                api.tercih_edilen = 0
                api.httpd = None
                api.thread = None

                def blocked_dns(address):
                    release_dns.wait(3)
                    return (address, [], [address])

                def start():
                    try:
                        api.start()
                        started.set()
                    except Exception as exc:
                        errors.append(exc)

                with patch.object(socket, 'getfqdn', side_effect=blocked_dns), \
                     patch.object(api, '_endpoint_yaz'):
                    worker = threading.Thread(target=start, daemon=True)
                    worker.start()
                    try:
                        self.assertTrue(started.wait(.5),
                                        'LocalAPI.start waits for reverse DNS before serving HTTP')
                        self.assertEqual(errors, [])
                        client = http.client.HTTPConnection(
                            '127.0.0.1', api.httpd.server_address[1], timeout=1)
                        try:
                            client.request('GET', '/ping')
                            response = client.getresponse()
                            self.assertEqual(response.status, 200)
                            self.assertIn(b'AfuDM', response.read())
                        finally:
                            client.close()
                    finally:
                        release_dns.set()
                        worker.join(4)
                        if api.httpd:
                            api.stop()


if __name__ == '__main__':
    unittest.main()
