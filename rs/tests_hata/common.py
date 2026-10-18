"""Owned processes, local range/web-seed server, HTTP requests and tree metrics."""
from __future__ import annotations
import hashlib, http.client, http.server, json, os, secrets, shutil, socket
import sqlite3, subprocess, sys, threading, time
from contextlib import closing
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT.parent/'engine'
OUT=ROOT/'tests_hata/rapor'
OUT.mkdir(exist_ok=True)
HIDDEN={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
BLOCK=bytes(range(256))*256

def redact(v):
    if isinstance(v,dict):return {k:('[REDACTED]' if any(x in k.lower() for x in ('token','secret','gizli','cookie','authorization')) else redact(x)) for k,x in v.items()}
    if isinstance(v,list):return [redact(x) for x in v]
    return v

def emit(name,data):
    (OUT/(name+'.json')).write_text(json.dumps(redact(data),ensure_ascii=False,indent=2,default=str),encoding='utf-8',newline='\n')

def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); p=s.getsockname()[1]
    assert p not in (6810,6811,6821)
    return p

def request(p,path,body=None,token=None,headers=None,raw=None,method=None,host='127.0.0.1'):
    assert p not in (6810,6811), 'User instance is forbidden'
    h={'Content-Type':'application/json',**(headers or {})}
    if token is not None: h['X-AfuDM-Token']=token
    data=raw if raw is not None else (json.dumps(body,ensure_ascii=False).encode() if body is not None else None)
    c=http.client.HTTPConnection(host,p,timeout=12)
    try:
        verb=method or ('POST' if data is not None else 'GET')
        if data and len(data)>512*1024:
            # Read an early 413 while the body is still being sent. Windows can abort
            # sendall after a server closes; that must not discard its HTTP response.
            c.putrequest(verb,path)
            if not any(k.lower()=='content-length' for k in h):h['Content-Length']=str(len(data))
            for k,v in h.items():c.putheader(k,v)
            c.endheaders()
            sock=c.sock
            def send_body():
                try:sock.sendall(data)
                except OSError:pass
            sender=threading.Thread(target=send_body,daemon=True)
            sender.start()
        else:
            c.request(verb,path,data,h)
        r=c.getresponse(); b=r.read()
        try: v=json.loads(b)
        except Exception: v={'raw':b[:140].decode('utf-8',errors='replace')}
        return {'status':r.status,'json':v}
    except Exception as e: return {'status':0,'exception':type(e).__name__}
    finally:
        c.close()
        if 'sender' in locals():
            sender.join(timeout=1)
            if sender.is_alive():
                try:sock.shutdown(socket.SHUT_RDWR)
                except OSError:pass
                sender.join(timeout=1)

def shape(v):
    if isinstance(v,dict): return {k:shape(x) for k,x in v.items()}
    if isinstance(v,list): return ['empty'] if not v else [shape(v[0])]
    if v is None: return 'null'
    if isinstance(v,bool): return 'bool'
    if isinstance(v,(int,float)): return 'number'
    return 'string'

def integrity(base):
    try:
        with closing(sqlite3.connect(base/'data/afudm.db')) as db:
            return db.execute('pragma integrity_check').fetchone()[0]
    except Exception as e: return str(e)

class App:
    def __init__(self,kind,root,exe=None):
        assert kind == 'rs', 'Only isolated Rust instances are supported'
        self.kind=kind; self.base=Path(root)/kind; self.base.mkdir(exist_ok=True)
        self.secret=secrets.token_hex(32); self.port=port(); self.rpcport=port(); self.gate=port(); self.panelport=port()
        self.proc=None; self.handles=[]; self.owned_history={}; self.exe=exe or ROOT/'tests_hata/bin/AfuDM_test.exe'
        (self.base/'engine').mkdir(exist_ok=True)
        for name in ('aria2c.exe','yt-dlp.exe'):
            if (ENGINE/name).exists(): shutil.copy2(ENGINE/name,self.base/'engine'/name)
        shutil.copy2(self.exe,self.base/'AfuDM.exe')
    def start(self):
        env={k:v for k,v in os.environ.items() if not k.startswith('AFUDM_')}
        env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',AFUDM_PORT=str(self.port),AFUDM_TEST_TOKEN=self.secret,AFUDM_TEST_RPC_PORT=str(self.rpcport))
        # Fresh store with automatic actions disabled, before boot threads run.
        data=self.base/'data';data.mkdir(exist_ok=True)
        (data/'trackers.txt').touch()  # fresh empty cache prevents external tracker-list fetches
        with sqlite3.connect(data/'afudm.db') as db:
            db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            for k,v in {'download_dir':str(self.base/'downloads'),'kaydetme_penceresi':False,
                        'guncelleme_otomatik':False,'clipboard_watch':False,
                        'notify_telegram':False,'windows_notifications':False,'sunucu_acik':False,'sunucu_port':self.panelport,'telefon_acik':False,'lan_erisimi':False,'automation_enabled':False,'tracker_otomatik_tara':False,'auto_update_trackers':False}.items():
                db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(k,json.dumps(v)))
        db.close()
        log=open(OUT/(self.kind+'_runtime.log'),'a',encoding='utf-8');self.handles.append(log)
        cmd=[str(self.base/'AfuDM.exe')]
        (self.base/'stop').unlink(missing_ok=True)
        for f in ('ready.json','data/test_endpoint.json'):(self.base/f).unlink(missing_ok=True)
        (data/'test_boot_error.json').unlink(missing_ok=True)
        self.proc=subprocess.Popen(cmd,cwd=self.base,env=env,stdout=log,stderr=subprocess.STDOUT,**HIDDEN)
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            if self.proc.poll() is not None: raise RuntimeError(f'{self.kind} exited {self.proc.returncode}, see runtime log')
            if (data/'test_boot_error.json').exists():
                raise RuntimeError(f'{self.kind}: '+(data/'test_boot_error.json').read_text())
            f=self.base/'data/test_endpoint.json'
            if f.exists():
                try:
                    v=json.loads(f.read_text());self.gate=v['port']
                    if self.call('surum_bilgi',[])['status']==200:
                        self.token=(data/'api_token.txt').read_text().strip()
                        return
                except (OSError,ValueError,KeyError): pass
            time.sleep(.25)
        raise RuntimeError(f'{self.kind} startup timeout')
    def call(self,name,args): return request(self.gate,'/_test/api_call',{'name':name,'args':args},self.secret)
    def http(self,path,body=None,**kw): return request(self.port,path,body,kw.pop('token',self.token),**kw)
    def tree(self):
        if not self.proc or self.proc.poll() is not None: return []
        try: return [psutil.Process(self.proc.pid),*psutil.Process(self.proc.pid).children(recursive=True)]
        except psutil.Error: return []
    def owned(self):
        found={p.pid:p for p in self.tree()}
        prefix=os.path.normcase(str(self.base.resolve()))+os.sep
        for p in psutil.process_iter(['exe','cmdline']):
            try:
                exe=os.path.normcase(p.info['exe'] or '')
                if exe.startswith(prefix) or str(self.base) in (p.info['cmdline'] or []):found[p.pid]=p
            except psutil.Error:pass
        self.owned_history.update(found)
        return list(found.values())
    def kill(self):
        tree=self.owned()
        # Taskkill is scoped to the exact Popen PID, never a name/global process query.
        if self.proc and self.proc.poll() is None:
            result=subprocess.run(['taskkill','/PID',str(self.proc.pid),'/T','/F'],capture_output=True,**HIDDEN)
            self.last_taskkill_exit=result.returncode
            # Some managed Windows sandboxes refuse taskkill; terminate owned handles directly.
            if self.proc.poll() is None:
                self.proc.kill()
            self.proc.wait(timeout=15)
        for p in tree:
            try:
                if p.is_running(): p.kill()
            except psutil.Error: pass
        _,alive=psutil.wait_procs(tree,timeout=10)
        if alive:raise RuntimeError("owned processes did not stop: "+str([p.pid for p in alive]))
    def close(self):
        self.kill()
        for h in self.handles: h.close()

def sample(app):
    v={'working_set':0,'private_bytes':0,'cpu_seconds':0.,'write_bytes':0,'processes':0}
    for p in app.tree():
        try:
            mem=p.memory_info(); cpu=p.cpu_times(); io=p.io_counters()
            v['working_set']+=mem.rss;v['private_bytes']+=getattr(mem,'private',mem.vms)
            v['cpu_seconds']+=cpu.user+cpu.system;v['write_bytes']+=io.write_bytes;v['processes']+=1
        except psutil.Error: pass
    return v

class FileServer(http.server.ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self):
        super().__init__(('127.0.0.1',0),FileHandler)
        self.files={}; self.ranges=[];self.limit=0
        threading.Thread(target=self.serve_forever,daemon=True).start()
    @property
    def url(self): return f'http://127.0.0.1:{self.server_port}'
    def add(self,name,size,speed=0): self.files['/'+name]=(size,speed);return self.url+'/'+name

class FileHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_HEAD(self): self.send(False)
    def do_GET(self): self.send(True)
    def send(self,body):
        item=self.server.files.get(self.path.split('?')[0])
        if item is None: self.send_error(404); return
        if isinstance(item,bytes):
            self.send_response(200);self.send_header('Content-Length',str(len(item)));self.end_headers()
            if body: self.wfile.write(item)
            return
        size,speed=item;start=0;end=size-1
        r=self.headers.get('Range','')
        if r.startswith('bytes='):
            left,right=r[6:].split('-');start=int(left or 0);end=min(int(right) if right else size-1,size-1)
        if start>=size: self.send_error(416);return
        if body: self.server.ranges.append({'path':self.path,'start':start,'end':end,'at':time.time()})
        self.send_response(206 if r else 200)
        self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes')
        self.send_header('ETag','"t2-deterministic-v1"');self.send_header('Content-Type','application/octet-stream')
        if r: self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        if not body:return
        sent=0;t=time.monotonic()
        try:
            while start+sent<=end:
                pos=(start+sent)%len(BLOCK); n=min(len(BLOCK)-pos,end-start+1-sent)
                self.wfile.write(BLOCK[pos:pos+n]);sent+=n
                cap=speed or self.server.limit
                if cap: time.sleep(max(0,sent/cap-(time.monotonic()-t)))
        except (ConnectionError,OSError): pass

def digest_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def expected_digest(size):
    h=hashlib.sha256()
    for _ in range(size//len(BLOCK)):h.update(BLOCK)
    h.update(BLOCK[:size%len(BLOCK)]);return h.hexdigest()

def bencode(x):
    if isinstance(x,int):return b'i'+str(x).encode()+b'e'
    if isinstance(x,str):x=x.encode()
    if isinstance(x,bytes):return str(len(x)).encode()+b':'+x
    if isinstance(x,list):return b'l'+b''.join(map(bencode,x))+b'e'
    return b'd'+b''.join(bencode(k)+bencode(x[k]) for k in sorted(x))+b'e'
