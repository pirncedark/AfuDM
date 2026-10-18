"""301B: real aria2 tellStatus error contract, isolated ports and temporary files."""
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.request


class Forbidden(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(403)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def log_message(self, *_):
        pass


class Aria403Contract(unittest.TestCase):
    def test_real_tell_status_reports_22_and_403(self):
        binary = Path(__file__).resolve().parents[2] / 'engine' / 'aria2c.exe'
        self.assertTrue(binary.is_file(), 'repo engine/aria2c.exe required')
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0))
            port = reserve.getsockname()[1]
        self.assertNotIn(port, (6810, 6811))
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Forbidden)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        def rpc(method, params):
            request = urllib.request.Request(
                f'http://127.0.0.1:{port}/jsonrpc',
                json.dumps({'jsonrpc': '2.0', 'id': '301B', 'method': 'aria2.' + method, 'params': params}).encode(),
                {'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=2) as response:
                value = json.load(response)
            if 'error' in value:
                raise RuntimeError(value['error']['code'])
            return value['result']
        try:
            with tempfile.TemporaryDirectory(prefix='afudm-301b-') as root:
                flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
                process = subprocess.Popen([
                    str(binary), '--enable-rpc=true', '--rpc-listen-all=false',
                    f'--rpc-listen-port={port}', '--enable-dht=false', '--bt-enable-lpd=false',
                    '--disable-ipv6=true', '--no-conf=true', '--console-log-level=error',
                    f'--dir={root}'], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
                try:
                    deadline = time.monotonic() + 15
                    while True:
                        try:
                            rpc('getVersion', [])
                            break
                        except Exception:
                            if time.monotonic() > deadline:
                                raise
                            time.sleep(.1)
                    gid = rpc('addUri', [[f'http://127.0.0.1:{server.server_port}/file.zip'], {'max-tries': '1'}])
                    deadline = time.monotonic() + 15
                    while True:
                        status = rpc('tellStatus', [gid, ['status', 'errorCode', 'errorMessage']])
                        if status['status'] == 'error':
                            break
                        self.assertLess(time.monotonic(), deadline)
                        time.sleep(.1)
                    self.assertEqual(status['errorCode'], '22')
                    self.assertIn('403', status['errorMessage'])
                    print('Real tellStatus: ' + json.dumps(status), flush=True)
                finally:
                    process.terminate()
                    process.wait(timeout=10)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
