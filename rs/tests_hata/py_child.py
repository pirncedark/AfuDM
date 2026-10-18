"""Read-only Python source, isolated runtime; no webview.start or windows."""
import os, sys, json, socket, threading, time, http.server, inspect
from pathlib import Path
sys.dont_write_bytecode = True
source, base, port, rpc, gate, secret = sys.argv[1:]
base = Path(base)
os.environ['AFUDM_DATA_ROOT'] = str(base)
os.environ['AFUDM_RPC_PORT'] = rpc
sys.path.insert(0, source)
from core.baslangic import uyku_yollarini_ayarla
uyku_yollarini_ayarla()
from core import paths, daemon, engines
# app import invokes redirect again: prevent double remapping; BASE itself is isolated.
import core.baslangic
core.baslangic.uyku_yollarini_ayarla = lambda: None
paths.BASE = base
paths.ENGINE = base/'engine'
paths.ARIA2C = paths.ENGINE/'aria2c.exe'
paths.UI = Path(source)/'ui'
paths.EXTENSION = base/'extension'
daemon.RPC_PORT = daemon.RPC_PORT_SON = int(rpc)
original_engine_args = daemon._args
def isolated_engine_args(*args, **kwargs):
    with socket.socket() as peer:
        peer.bind(('127.0.0.1', 0)); peer_port = peer.getsockname()[1]
    return original_engine_args(*args, **kwargs) + [
        '--enable-dht=false', '--bt-enable-lpd=false', '--disable-ipv6=true',
        f'--listen-port={peer_port}']
daemon._args = isolated_engine_args
engines.eksikler = lambda *a, **kw: []  # suppress Api.__init__ optional Internet installers
from core.manager import Manager
from core.servis import AfuDMServis
from core import ornek
from api.server import LocalAPI, _Handler
from app import Api
# app sets an expanded range: pin it back to the one reserved test port.
daemon.RPC_PORT = daemon.RPC_PORT_SON = int(rpc)
paths.ensure_dirs()
manager = Manager()
manager.start()
for k,v in {'download_dir':str(base/'downloads'), 'kaydetme_penceresi':False,
            'guncelleme_otomatik':False,'clipboard_watch':False,
            'notify_telegram':False,'windows_notifications':False}.items(): manager.store.set(k,v)
servis = AfuDMServis(manager, kip=ornek.KIP_HEADLESS)
_Handler.servis = servis
local = LocalAPI(manager, port=int(port), lan=False)
actual = local.start()
api = Api(manager, local, servis)
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_POST(self):
        if self.headers.get('X-AfuDM-Token') != secret or self.headers.get('Origin'):
            self.send_error(401); return
        try:
            v=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
            result=getattr(api,v['name'])(*v['args'])
        except Exception as e: result={'__exception__':type(e).__name__, 'message':str(e)[:160]}
        raw=json.dumps(result,ensure_ascii=False,default=str).encode()
        self.send_response(200); self.send_header('Content-Length',str(len(raw)))
        self.end_headers(); self.wfile.write(raw)
srv=http.server.ThreadingHTTPServer(('127.0.0.1',int(gate)),Handler)
threading.Thread(target=srv.serve_forever,daemon=True).start()
(base/'ready.json').write_text(json.dumps({'port':actual,'gate':srv.server_port}))
while not (base/'stop').exists(): time.sleep(.2)
srv.shutdown(); local.stop(); manager.stop()
