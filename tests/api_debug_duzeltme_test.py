import io
import queue
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import server, web
from core import baslangic, cerez, paylasim_sunucusu as share, tunel


def handler(cls, headers=None):
    h = object.__new__(cls)
    h.headers = headers or {}
    h.path = '/s/test'
    h.wfile = io.BytesIO()
    h.send_response = lambda code: setattr(h, 'status', code)
    h.response_headers = {}
    h.send_header = lambda k, v: h.response_headers.update({k: v})
    h.end_headers = lambda: None
    return h


class ApiFixTests(unittest.TestCase):
    def test_delete_false(self):
        svc = NS(kontrol=Mock(return_value={'ok': True}))
        h = handler(web._Handler)
        h.sunucu = NS(servis=svc)
        for value in ('false', '0', '', 'no', False, None):
            h._post_calistir('/api/kontrol', {'action':'remove', 'gid':'g', 'delete_files':value}, {})
            self.assertIs(svc.kontrol.call_args.args[2], False)
            self.assertIs(server._boolean_al({'delete_files':value}, 'delete_files'), False)

    def test_body_limits(self):
        for length, status in (('-1', 400), ('bad', 400), (str(8*1024*1024+1), 413)):
            h = handler(server._Handler, {'Content-Length':length})
            h._rate_allowed = lambda: True
            h._authorized = lambda _: True
            h._hata = lambda code, *args: setattr(h, 'status', code)
            h._send = lambda code, data: setattr(h, 'status', code)
            h.rfile = io.BytesIO(b'{}')
            h.connection = Mock()
            h.path = '/unknown'
            h.do_POST()
            self.assertEqual(h.status, status)
            self.assertEqual(h.rfile.tell(), 0)

    def test_socket_timeouts(self):
        for cls in (server._Handler, web._Handler):
            h = handler(cls)
            h.request = Mock()
            with patch('http.server.BaseHTTPRequestHandler.setup'):
                h.setup()
            h.request.settimeout.assert_called_once()
            self.assertGreater(h.request.settimeout.call_args.args[0], 0)

    def test_body_errors_and_valid_input(self):
        for cls, method, limit in ((server._Handler, '_body', 8*1024*1024),
                                   (web._Handler, '_govde', 2_000_000)):
            for raw, length, expected in ((b'{}', '2', None), (b'{}', '3', 400),
                                          (b'[]','2',400), (b'x','1',400),
                                          (b'',str(limit+1),413)):
                h = handler(cls, {'Content-Length':length})
                h.rfile = io.BytesIO(raw)
                if expected is None:
                    self.assertEqual(getattr(h,method)(), {})
                else:
                    with self.assertRaises(server._GovdeHatasi) as error:
                        getattr(h,method)()
                    self.assertEqual(error.exception.status,expected)
            h = handler(cls, {'Content-Length':'2'})
            h.rfile = Mock(read=Mock(side_effect=socket.timeout()))
            with self.assertRaises(server._GovdeHatasi) as error:
                getattr(h,method)()
            self.assertEqual(error.exception.status,408)
            self.assertTrue(h.close_connection)

    def test_startup_success_replaces_and_failure_cleans(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(baslangic,'KLASOR',Path(tmp)), patch.object(baslangic,'_kisayol_argumani',return_value='old'), patch.object(baslangic,'hedef',return_value=(sys.executable,'new')):
            p = baslangic.kisayol_yolu()
            p.write_bytes(b'old')
            def create(cmd, **kwargs):
                target = Path(cmd[cmd.index('-KisayolYolu')+1])
                self.assertNotEqual(target,p)
                self.assertEqual(p.read_bytes(),b'old')
                target.write_bytes(b'new')
                return NS(returncode=0,stdout='',stderr='')
            with patch.object(baslangic.subprocess,'run',side_effect=create):
                baslangic.ac()
            self.assertEqual(p.read_bytes(),b'new')
            self.assertEqual(list(Path(tmp).iterdir()),[p])
            with patch.object(baslangic.subprocess,'run',return_value=NS(returncode=1,stdout='',stderr='failed')):
                with self.assertRaises(OSError):
                    baslangic.ac()
            self.assertEqual(p.read_bytes(),b'new')
            self.assertEqual(list(Path(tmp).iterdir()),[p])

    def test_tunnel_queue_bounded_and_drained(self):
        drained = threading.Event()
        def logs():
            yield 'https://unit.trycloudflare.com'
            for _ in range(5000):
                yield 'log line'
            drained.set()
        queues = []
        original = queue.Queue
        def make_queue(*a, **kw):
            q = original(*a, **kw)
            queues.append(q)
            return q
        with patch.object(tunel.queue, 'Queue', make_queue):
            url = tunel.TunnelManager('unused', timeout=1)._read_url(NS(stdout=logs(), poll=lambda:None))
        self.assertEqual(url, 'https://unit.trycloudflare.com')
        self.assertTrue(drained.wait(2))
        self.assertGreater(queues[0].maxsize, 0)
        self.assertLessEqual(queues[0].qsize(), 1)

    def stream(self, cls, content, range_value=None, head=False):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'data.bin'
            p.write_bytes(content)
            h = handler(cls, {'Range':range_value} if range_value is not None else {})
            if cls is share._PaylasimHandler:
                h.shares = {'test':{'path':str(p)}}
                h._serve(head)
            else:
                h._dosya_akis_gonder(p)
            return h

    def test_internet_suffix(self):
        h = self.stream(share._PaylasimHandler, bytes(range(100)), 'bytes=-10')
        self.assertEqual(h.status, 206)
        self.assertEqual(h.wfile.getvalue(), bytes(range(90,100)))
        self.assertEqual(h.response_headers['Content-Range'], 'bytes 90-99/100')

    def test_local_ranges(self):
        for range_value, status, expected in (
            ('bytes=-10',206,bytes(range(90,100))), ('bytes=0-999',206,bytes(range(100))),
            ('bytes=20-10',416,b''), ('bytes=100-',416,b''), ('oops',416,b''),
            ('bytes=-0',416,b''), ('bytes=0-1,5-6',416,b'')):
            h = self.stream(server._Handler, bytes(range(100)), range_value)
            self.assertEqual(h.status, status, range_value)
            self.assertEqual(h.wfile.getvalue(), expected, range_value)
            self.assertEqual(int(h.response_headers['Content-Length']),len(expected))

    def test_empty_shares(self):
        for cls in (share._PaylasimHandler,server._Handler):
            h = self.stream(cls,b'')
            self.assertEqual(h.status,200)
            self.assertEqual(h.response_headers['Content-Length'],'0')
            h = self.stream(cls,b'', 'bytes=0-')
            self.assertEqual(h.status,416)
            self.assertEqual(h.response_headers['Content-Range'],'bytes */0')
        h = self.stream(share._PaylasimHandler,b'',head=True)
        self.assertEqual(h.response_headers['Content-Length'],'0')

    def test_profile_origins(self):
        h = handler(web._Handler)
        h.sunucu = NS(port=1234, lan_ip='', servis=NS(
            store=NS(get=lambda _: 'https://old.example'),
            sunucu_ayarlari=lambda:{'originler':'https://profile.example'}))
        self.assertIn('https://profile.example',h._izinli_originler())
        self.assertNotIn('https://old.example',h._izinli_originler())

    def test_cookie_infinity(self):
        for date in ('1e309', '-1e309', 'nan'):
            result = cerez.temizle([{'name':'a','value':'b','domain':'example.com','expirationDate':date}])
            self.assertEqual(result[0]['expirationDate'],0)

    def test_startup_failure_keeps_old(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(baslangic,'KLASOR',Path(tmp)), patch.object(baslangic,'_kisayol_argumani',return_value='old'):
            p = baslangic.kisayol_yolu()
            for target, error in (('missing.exe',RuntimeError), (sys.executable,OSError)):
                p.write_bytes(b'old shortcut')
                with patch.object(baslangic,'hedef',return_value=(target,'new')), patch.object(baslangic.subprocess,'run',side_effect=OSError('failed')):
                    with self.assertRaises(error):
                        baslangic.ac()
                self.assertEqual(p.read_bytes(),b'old shortcut')

if __name__ == '__main__':
    unittest.main(verbosity=2)
