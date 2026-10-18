"""T2 scenarios. Every status is asserted; missing evidence is a failure."""
from __future__ import annotations
import collections, hashlib, json, re, sqlite3, time
from pathlib import Path
from common import *

def resource(apps,server,idle=300):
    rows=[]
    def measure(phase,seconds):
        start=time.monotonic(); prev={a.kind:sample(a) for a in apps};last=start
        while time.monotonic()-start<seconds:
            time.sleep(min(2,max(.01,seconds-(time.monotonic()-start))))
            now=time.monotonic()
            for a in apps:
                v=sample(a);p=prev[a.kind];dt=now-last
                rows.append({'phase':phase,'side':a.kind,'elapsed':round(now-start,2),**v,
                             'cpu_percent':max(0,(v['cpu_seconds']-p['cpu_seconds'])/dt*100),
                             'write_mib_s':max(0,(v['write_bytes']-p['write_bytes'])/dt/2**20)})
                prev[a.kind]=v
            last=now
            emit('resources_raw',rows)
            if int(now-start)%30<2: print(f'RAM {phase}: {int(now-start)}/{seconds}s',flush=True)
        emit('resources_raw',rows)
    measure('idle',idle)
    outputs=[]
    for phase,count,size in [('1GiB',1,1024**3),('3_concurrent',3,128*1024**2)]:
        server.limit=24*1024**2
        for a in apps:
            for i in range(count):
                name=f'{phase}_{a.kind}_{i}.bin';url=server.add(name,size)
                outputs.append((a,name,size,a.http('/add',{'url':url,'split':1,'max_conn_per_server':1})))
        measure(phase,60)
        for a,name,size,r in outputs:
            if not name.startswith(phase):continue
            p=a.base/'downloads'/name
            # Completion requires content hash, not preallocated file length.
            outputs[outputs.index((a,name,size,r))]=(a,name,size,{**r,'complete':p.exists() and not Path(str(p)+'.aria2').exists(),
                'sha_ok':p.exists() and p.stat().st_size==size and digest_file(p)==expected_digest(size)})
        emit('resource_downloads',[{'side':a.kind,'name':n,'size':s,**r} for a,n,s,r in outputs])
    server.limit=0
    summary=[]
    for phase in ('idle','1GiB','3_concurrent'):
        for side in ('rs',):
            rr=[r for r in rows if r['phase']==phase and r['side']==side]
            summary.append({'phase':phase,'side':side,'samples':len(rr),
                'working_set_mib_avg':sum(r['working_set'] for r in rr)/len(rr)/2**20,
                'private_mib_avg':sum(r['private_bytes'] for r in rr)/len(rr)/2**20,
                'cpu_percent_avg':sum(r['cpu_percent'] for r in rr)/len(rr),
                'write_mib_s_avg':sum(r['write_mib_s'] for r in rr)/len(rr),
                'max_processes':max(r['processes'] for r in rr)})
    ok=idle>=300 and all(r['json'].get('ok') and r.get('sha_ok') and r.get('complete') for _,_,_,r in outputs)
    emit('resources',{'status':'GECTI' if ok else 'KALDI','idle_seconds':idle,'summary':summary})

def fuzz(apps,server):
    # Route inventory is derived from production Rust routers (including chained .post()).
    files=[ROOT/'crates/afudm-api/src/lib.rs',ROOT/'app/src/windows_rota.rs',
           *[ROOT/f'crates/afudm-extras/src/{part}/mod.rs' for part in ('g1','g2','h')]]
    routes=set()
    for f in files:
        for m in re.finditer(r'\.route\(\s*"([^"]+)"\s*,(.*?)(?=\.route\(|\.with_state\(|\n\})',f.read_text(encoding='utf-8'),re.S):
            if re.search(r'\bpost\(',m[2]):routes.add(m[1])
    # Dedicated listener lifecycle routes are intentionally excluded: they can quit/open UI.
    cases=[('broken_json',b'{',None),('huge',b'{"x":"'+b'x'*(9*1024**2)+b'"}',None),
           ('list',b'[]',None),('null',b'null',None),('bool',b'true',None),
           ('empty',b'{}',None),('wrong_types',json.dumps({'url':[], 'gid':{},'action':3,'dest_dir':False}).encode(),None),
           ('unicode',json.dumps({'url':server.url+'/\u0130\u011fd\u0131r/\u4f60\u597d/\U0001f600','filename':'\u0130\u011fd\u0131r_\u65e5\u672c\U0001f600.bin'}).encode(),None),
           ('traversal',json.dumps({'url':server.url+'/missing','dest_dir':'..\\escape_t2','filename':'..\\escape_t2'}).encode(),None),
           ('file',b'{"url":"file:///invalid-t2"}',None),('javascript',b'{"url":"javascript:alert(1)"}',None),
           ('no_token',b'{}','none'),('wrong_token',b'{}','wrong'),('old_token',b'{}','old'),
           ('wrong_origin',b'{}','origin')]
    rows=[];old={a.kind:a.token for a in apps}
    for a in apps:
        a.http('/token/rotate',{})
        a.token=(a.base/'data/api_token.txt').read_text().strip()
    started=time.monotonic();sent=0
    for route in sorted(routes):
        for name,raw,mode in cases:
            if route=='/tracker/tara' and name in ('empty','wrong_types','unicode','traversal','file','javascript'):
                rows.append({'route':route,'case':name,'skip':'empty gid starts external tracker scan','failure':False,'masked_429':False,'difference':False})
                continue
            # Keep below each production limiter; otherwise 429 would hide body handling.
            if sent and sent%95==0:
                wait=max(0,61-(time.monotonic()-started));
                if wait: print(f'FUZZ rate-limit window: {wait:.0f}s',flush=True);time.sleep(wait)
                started=time.monotonic()
            row={'route':route,'case':name}
            for a in apps:
                token=None if mode=='none' else ('invalid-t2' if mode=='wrong' else old[a.kind] if mode=='old' else a.token)
                h={'Origin':'https://evil.invalid'} if mode=='origin' else {}
                if route=='/add_blob' and name=='huge':
                    h['Content-Length']=str(512*1024**2+1)
                    payload=b''
                else:payload=raw
                r=a.http(route,raw=payload,method='POST',token=token,headers=h)
                row[a.kind]=redact(r)
                # /rotate is body-independent; always refresh current credential.
                a.token=(a.base/'data/api_token.txt').read_text().strip()
            row['difference']=False  # Rust-only: no archived implementation comparison
            # Disconnects, server errors and process exits always fail the Rust check.
            row['failure']=any(row[a.kind]['status']==0 or row[a.kind]['status']>=500 or a.proc.poll() is not None for a in apps)
            row['masked_429']=any(row[a.kind]['status']==429 for a in apps)
            rows.append(row);sent+=1
        print(f'FUZZ {route}: {len(rows)} requests/side',flush=True)
        emit('fuzz_rows',rows)
    # Positive local download URL with escaped destination proves traversal containment.
    containment=[]
    for a in apps:
        sentinel=a.base/'escape_t2'
        r=a.http('/add',{'url':server.add('escape.bin',65536),'dest_dir':str(sentinel)})
        time.sleep(.5)
        containment.append({'side':a.kind,'response':r,'outside_downloads_exists':sentinel.exists()})
    emit('fuzz',{'status':'GECTI' if not any(r['failure'] or r['masked_429'] for r in rows) and not any(r['outside_downloads_exists'] for r in containment) else 'KALDI',
        'routes':sorted(routes),'cases':len(rows),'errors_500_or_disconnect':sum(r['failure'] for r in rows),
        'differences':sum(r['difference'] for r in rows),'masked_429':sum(r['masked_429'] for r in rows),
        'containment':containment,'limitations':['No full-system write tracing; sentinel checks cover tested escape targets.',
        'Listener lifecycle POSTs can open windows or stop processes; excluded by explicit user safety requirement.']})

SKIP={
 'reliability_health':'test-only IdleRpc placeholder; production RPC ports forbidden',
 'chrome_hazirla':'may install browser using external Internet',
 'seed_dosya_ekle':'empty default opens file dialog',
 'proxy_testi':'connectivity test can use external Internet',
 'tracker_tara':'tracker scan can access external Internet',
 'kapat':'process exit','simdi_uyu':'would suspend user computer',
 'baslangic_ayarla':'user startup registry','torrent_iliskilendir':'user registry',
 'varsayilan_uygulama_ekrani':'opens settings window','klasor_gozat':'dialog',
 'dosya_sec_ve_paylas':'dialog','open_download_dir':'Explorer window',
 'tracker_klasoru_ac':'Explorer window','eklenti_klasoru_ac':'Explorer window',
 'sunucu_panel_ac':'browser window','panoya_kopyala':'user clipboard',
 'panodan_oku':'user clipboard','chrome_kopyala':'user clipboard',
 'chrome_ac':'browser window','chrome_otomatik':'browser/registry',
 'guncelleme_kontrol':'external GitHub request', 'yerelden_sor':'download dialog',
 'tarayicidan_sor':'download dialog','ana_pencere_kapandi':'window lifecycle',
 'reliability_restart_engine':'Rust daemon scans production RPC port range',
}

# Valid recovery inputs are checked separately from invalid-input robustness.
BRIDGE_ATLA={'windows_integration_apply','windows_integration_remove'}
BRIDGE_GECERLI={'reliability_restore','reliability_recovery_preview','windows_integration_test'}

def hazirla_indirme(a,server,timeout=60):
    """Izole veriye yerel dosya sunucusundan kucuk bir indirme ekler, tamamlanmasini bekler; id doner."""
    import sqlite3
    r=a.http('/add',{'url':server.add('gecerli_t2.bin',65536)})
    rid=(r.get('json') or {}).get('id')
    if rid is None:return None
    db=a.base/'data'/'afudm.db';t=time.monotonic()
    while time.monotonic()-t<timeout:
        con=sqlite3.connect(str(db))
        try:satir=con.execute('SELECT status FROM downloads WHERE id=?',(rid,)).fetchone()
        except sqlite3.Error:satir=None
        finally:con.close()
        if satir and satir[0]=='complete':return int(rid)
        time.sleep(1)
    return None

def bridge_gecerli_args(name,a,server=None):
    """Her uygulama kendi izole verisinden gecerli bir girdi uretir; uretilemezse None."""
    import sqlite3
    if name=='windows_integration_test':return ['torrent']
    if name=='reliability_recovery_preview':
        rid=hazirla_indirme(a,server)
        return [rid] if rid is not None else None
    if name=='reliability_restore':
        zips=sorted((a.base/'data'/'backups').glob('*.zip'),key=lambda p:p.stat().st_mtime)
        return [str(zips[-1])] if zips else None
    return None

def bridge(apps,server):
    gate_checks=[]
    for a in apps:
        if a.kind!='rs':continue
        for label,tok,headers,raw,expected in [
            ('missing_token',None,{},b'{"name":"surum_bilgi","args":[]}',401),
            ('wrong_token','invalid-t2',{},b'{"name":"surum_bilgi","args":[]}',401),
            ('origin',a.secret,{'Origin':'https://evil.invalid'},b'{"name":"surum_bilgi","args":[]}',401),
            ('broken_json',a.secret,{},b'{',400),
            ('missing_fields',a.secret,{},b'{}',400),
            ('oversize',a.secret,{},b'x'*(1024**2+1),413),
            ('production_rpc_guard',a.secret,{},b'{"name":"reliability_health","args":[]}',403),
        ]:
            r=request(a.gate,'/_test/api_call',token=tok,headers=headers,raw=raw,method='POST')
            gate_checks.append({'case':label,'status':r['status'],'expected':expected,'passed':r['status']==expected})
    emit('gate_security',gate_checks)
    methods=json.loads((ROOT/'tests_hata/bridge_cases.json').read_text(encoding='utf-8'))
    rows=[]
    for name,case in sorted(methods.items()):
        reason=SKIP.get(name) or case.get('skip')
        if reason: rows.append({'name':name,'skip':reason});continue
        args=json.loads(json.dumps(case['args']).replace('__T2_URL__',server.url))
        if name=='klasor_yeni':args=['__T2_BASE__','nested-t2']
        if name=='eklenti_incele':args=['__T2_BASE__/missing.zip']
        if name=='motor_indir':args=['invalid-t2']
        if name=='sunucu_ayarla':args=[False]
        if name=='telefon_ayarla':args=[False]
        if name=='windows_integration_apply' or name=='windows_integration_remove':args=['invalid-t2']
        if name in BRIDGE_ATLA:
            rows.append({'name':name,'skip':'muaf: kayit defterine yazar (kullanici makinesi); harness yazmaz'});continue
        row={'name':name,'args':args}
        for a in apps:
            own=json.loads(json.dumps(args).replace('__T2_BASE__',str(a.base).replace('\\','\\\\')))
            r=a.call(name,own)
            # api_info and token rotation return credentials: compare shapes, never persist secrets.
            row[a.kind]={'status':r['status'],'shape':shape(r.get('json')),
                         'ok':r.get('json',{}).get('ok') if isinstance(r.get('json'),dict) else None,
                         'exception':r.get('json',{}).get('__exception__') if isinstance(r.get('json'),dict) else None}
            a.token=(a.base/'data/api_token.txt').read_text().strip()
        row['passed']=row['rs']['status']==200 and not row['rs']['exception']
        rows.append(row)
        print(f'BRIDGE {name}: passed={row["passed"]}',flush=True)
        emit('bridge_rows',rows)
    # Gecerli girdiler Rust bridge tarafindan istisnasiz islenmeli.
    for name in sorted(BRIDGE_GECERLI):
        row={'name':name+' [gecerli]','args':'per-app'}
        for a in apps:
            args=bridge_gecerli_args(name,a,server)
            if args is None:
                row[a.kind]={'status':None,'shape':None,'ok':None,'exception':'gecerli girdi uretilemedi'}
                continue
            r=a.call(name,args)
            row[a.kind]={'status':r['status'],'shape':shape(r.get('json')),
                         'ok':r.get('json',{}).get('ok') if isinstance(r.get('json'),dict) else None,
                         'exception':r.get('json',{}).get('__exception__') if isinstance(r.get('json'),dict) else None}
            a.token=(a.base/'data/api_token.txt').read_text().strip()
        row['passed']=row['rs']['status']==200 and row['rs']['shape'] is not None and not row['rs']['exception']
        rows.append(row)
        print(f'BRIDGE {row["name"]}: passed={row["passed"]}',flush=True)
        emit('bridge_rows',rows)
    called=[r for r in rows if 'skip' not in r]
    emit('bridge',{'status':'GECTI' if all(c['passed'] for c in gate_checks) and bool(called) and all(r['passed'] for r in called) else 'KALDI',
                  'unique_public_methods':len(methods),'called':len(called),'skipped':len(rows)-len(called),'differences':sum(not r['passed'] for r in called)})

def scan_dosya(path,limit):
    """Dosyayi 64 KiB parcalarla BLOCK ile karsilastirir; yazilmamis (sifir) ve bozuk parcalari sayar."""
    path=Path(path)
    if not path.exists() or limit<=0:return None
    n=bad=zero=0;ilk=None;off=0
    with open(path,'rb') as f:
        while off<limit:
            d=f.read(min(len(BLOCK),limit-off))
            if not d:break
            n+=1
            if d!=BLOCK[:len(d)]:
                bad+=1;ilk=off if ilk is None else ilk
                if d.count(0)==len(d):zero+=1
            off+=len(d)
    return {'chunks':n,'bad':bad,'zero':zero,'ilk_bad_offset':ilk}

def crash(apps,server):
    rows=[];size=192*1024**2
    for mode in ('http','torrent'):
        name=f'crash_{mode}.bin';url=server.add(name,size)
        # Aggregate app speed avoids multi-connection throughput bypassing server throttle.
        for a in apps:a.call('settings_save',[{'max_speed_kb':1024,'split':1,'max_conn_per_server':1}])
        if mode=='torrent':
            piece=1024**2;piece_hash=hashlib.sha1(BLOCK*(piece//len(BLOCK))).digest()
            torrent=bencode({'info':{'name':name,'length':size,'piece length':piece,'pieces':piece_hash*(size//piece)},
                              'url-list':url})
            server.files['/crash.torrent']=torrent
            for a in apps:(a.base/'crash.torrent').write_bytes(torrent)
        starts={a.kind:a.http('/add',{'url':url if mode=='http' else str(a.base/'crash.torrent')}) for a in apps}
        gids={k:v.get('json',{}).get('gid') for k,v in starts.items()}
        progress={};t=time.monotonic()
        while time.monotonic()-t<300:
            for a in apps:
                snap=a.call('snapshot',[]).get('json',{})
                # Search the snapshot recursively for the assigned gid.
                def find(v):
                    if isinstance(v,dict):
                        if v.get('gid')==gids[a.kind]:return v
                        for x in v.values():
                            r=find(x)
                            if r:return r
                    elif isinstance(v,list):
                        for x in v:
                            r=find(x)
                            if r:return r
                    return None
                row=find(snap) or {};progress[a.kind]=row
            done=[float(progress.get(a.kind,{}).get('completedLength',0) or 0)/size for a in apps]
            if all(x>=.4 for x in done):break
            if int(time.monotonic()-t)%30<2:print(f'CRASH {mode} progress {[round(x,3) for x in done]}',flush=True)
            time.sleep(2)
        pending=[]
        for a in apps:
            before=progress.get(a.kind,{})
            before_done=int(before.get('completedLength',0) or 0)
            # Save nothing explicitly: this is a real abrupt-crash durability test.
            control=a.base/'downloads'/(name+'.aria2')
            session=a.base/'data/aria2.session'
            info={'side':a.kind,'mode':mode,'add':starts[a.kind],
                  'before_done':before_done,'fraction':before_done/size,'control_exists':control.exists(),
                  'session_bytes':session.stat().st_size if session.exists() else None,
                  'at_40_percent':.4<=before_done/size<=.5}
            print(f'CRASH {mode} {a.kind}: stopping at {info["fraction"]:.1%}; session={info["session_bytes"]} bytes',flush=True)
            a.kill()
            info['taskkill_exit']=getattr(a,'last_taskkill_exit',None)
            info['pre_restart_scan']=scan_dosya(a.base/'downloads'/name,before_done//65536*65536)
            pending.append((a,info))
        for a,info in pending:
            print(f'CRASH {mode} {a.kind}: restarting; resume deadline 300 seconds',flush=True)
            mark=len(server.ranges);a.start()
            info['integrity']=integrity(a.base)
            # Speed reset after restart; record completed bytes before reset and all resumed ranges.
            info['restart_snapshot_shape']=shape(a.call('snapshot',[]).get('json'))
            a.call('settings_save',[{'max_speed_kb':0}])
            deadline=time.monotonic()+300
            file=a.base/'downloads'/name
            while time.monotonic()<deadline:
                if file.exists() and not Path(str(file)+'.aria2').exists():break
                time.sleep(1)
            info['resumed_ranges']=[r for r in server.ranges[mark:] if r['path'].split('?')[0]=='/'+name]
            info['post_scan']=scan_dosya(file,size)
            info['sha_ok']=file.exists() and file.stat().st_size==size and digest_file(file)==expected_digest(size)
            info['range_after_restart']=any(r['start']>0 for r in info['resumed_ranges'])
            info['status']='GECTI' if info['at_40_percent'] and info['control_exists'] and info['integrity']=='ok' and info['sha_ok'] and info['range_after_restart'] else 'KALDI'
            rows.append(info);emit('crash',rows)
            print(f'CRASH {mode} {a.kind}: {info["status"]}',flush=True)
    return rows

def network(apps):
    rows=[]
    try:
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.connect(('10.255.255.255',1));ip=sock.getsockname()[0];sock.close()
    except OSError:ip=None
    for a in apps:
        pp=port()
        setup=a.call('settings_save',[{'sunucu_port':pp,'sunucu_adres':'lan','sunucu_istek_limiti':1000}])
        key=a.call('sunucu_anahtar_olustur',['T2','yonetici','temporary'])
        opened=a.call('sunucu_ayarla',[True])
        # zaten:True ise panel onceki portta acik kalmis olabilir; gercek acilan port kullanilir.
        pp=opened.get('json',{}).get('port') or pp
        kv=key.get('json',{}); credential=kv.get('anahtar') or kv.get('gizli') or kv.get('key') or ''
        checks=[]
        for host in filter(None,['127.0.0.1',ip]):
            for label,h in [('none',{}),('invalid',{'X-AfuDM-Key':'invalid-t2'}),('valid',{'X-AfuDM-Key':credential}),
                            ('wrong_origin',{'X-AfuDM-Key':credential,'Origin':'https://evil.invalid'})]:
                checks.append({'host':'loopback' if host=='127.0.0.1' else 'LAN','case':label,
                               'result':request(pp,'/api/liste',headers=h,host=host)})
        lan=a.call('telefon_ayarla',[True]);lanchecks=[]
        if ip:
            for label,tok in [('none',None),('invalid','invalid-t2'),('valid',a.token)]:
                lanchecks.append({'case':label,'result':request(a.port,'/snapshot',token=tok,host=ip)})
        # Test gate must be absent from production and never bind to LAN.
        gate_lan=request(a.gate,'/_test/api_call',{'name':'surum_bilgi','args':[]},a.secret,host=ip) if ip else None
        a.call('telefon_ayarla',[False]);a.call('sunucu_ayarla',[False])
        checks_ok=all(c['result']['status']==(200 if c['case']=='valid' else 403 if c['case']=='wrong_origin' else 401) for c in checks)
        lan_ok=bool(lanchecks) and all(c['result']['status']==(200 if c['case']=='valid' else 401) for c in lanchecks)
        rows.append({'side':a.kind,'settings':setup,'opened':opened,'key_result_shape':shape(kv),
                     'panel':checks,'lan_opened_shape':shape(lan.get('json')),'lan':lanchecks,
                     'gate_lan_status':gate_lan['status'] if gate_lan else None,
                     'status':'GECTI' if checks_ok and lan_ok and gate_lan and gate_lan['status']==0 else 'KALDI'})
    emit('network',rows)
