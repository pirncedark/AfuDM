"""Scenario 3: copied production DB and real legacy updater against loopback release."""
import argparse, hashlib, http.server, json, os, shutil, sqlite3, subprocess, sys, tempfile, threading, time, zipfile
from common import *
from contextlib import closing

HELPER=r'''
import sys, os, json
from pathlib import Path
sys.dont_write_bytecode=True
source, base, api_url=sys.argv[1:]
sys.path.insert(0,source)
from core import paths,surum,guncelleme as g
paths.BASE=Path(base);paths.DATA=Path(base)/'data'
surum.SURUM='2.9.8'  # requested updater version; actual source version is recorded separately
# Only the release allowlist root is redirected to the local fake GitHub.
g.IZINLI_ONEK=api_url.rsplit('/',1)[0]+'/'
bilgi=g.kontrol(api_url)
r=g.indir_ve_dogrula(bilgi)
ready=g.hazir()
original=g.subprocess.Popen
calls=[]
def launch(cmd,**kw):
    script=Path(cmd[-1]);text=script.read_text(encoding='utf-8-sig')
    basepath=Path(base).resolve()
    for p in (paths.BASE,paths.DATA/'guncelleme/yeni/AfuDM',paths.DATA/'guncelleme/yedek'):
        assert p.resolve().is_relative_to(basepath), 'update script path outside sandbox'
    # Run the real copy/backup/rollback script. Capture only final relaunch, never open UI.
    marker=Path(base)/'launch_captured.txt'
    shim="function Start-Process { param([string]$FilePath) [System.IO.File]::WriteAllText('"+str(marker).replace("'","''")+"', $FilePath) }\n"
    script.write_text(shim+text,encoding='utf-8-sig')
    proc=original(cmd,**kw)
    calls.append(proc.pid)
    return proc
g.subprocess.Popen=launch
sys.frozen=True
applied=g.uygula()
(Path(base)/'update_api_result.json').write_text(json.dumps({'control':bilgi,'download':r,'ready':ready,'apply':applied,'launcher_pids':calls}),encoding='utf-8')
'''

def db_snapshot(path):
    with closing(sqlite3.connect(path)) as db:
        integrity=db.execute('pragma integrity_check').fetchone()[0]
        tables=[r[0] for r in db.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")]
        counts={t:db.execute('select count(*) from "'+t.replace('"','""')+'"').fetchone()[0] for t in tables}
        rows=list(db.execute('select key,value from settings order by key'))
        return {'integrity':integrity,'counts':counts,'settings_sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False).encode()).hexdigest(),
                'history_sha256':hashlib.sha256(repr(list(db.execute('select * from downloads order by id'))).encode()).hexdigest(),
                'user_version':db.execute('pragma user_version').fetchone()[0]}

def main():
    with tempfile.TemporaryDirectory(prefix='afudm_t2_update_') as tmp:
        root=Path(tmp);base=root/'install';(base/'data').mkdir(parents=True)
        oldexe=base/'AfuDM.exe';oldexe.write_bytes(b'T2-legacy-2.9.8-installation-placeholder')
        # Physical copies only: no SQLite connection to the live database.
        copied=[]
        for name in ('afudm.db','afudm.db-wal','afudm.db-shm'):
            src=SOURCE/'data'/name
            if src.is_file():shutil.copyfile(src,base/'data'/name);copied.append(name)
        before=db_snapshot(base/'data/afudm.db')
        shutil.copy2(ROOT/'tests_hata/bin/AfuDM_test.exe',base/'AfuDM.exe')
        result=subprocess.run([str(base/'AfuDM.exe'),'--t2-migrate-only'],cwd=base,capture_output=True,timeout=60,**HIDDEN)
        after=db_snapshot(base/'data/afudm.db')
        preserved=all(before[k]==after[k] for k in ('counts','settings_sha256','history_sha256'))
        migration_ok=result.returncode==0 and preserved and before['integrity']=='ok' and after['integrity']=='ok' and (base/'data/migration_complete.json').exists()
        emit('migration',{'status':'GECTI' if migration_ok else 'KALDI',
                         'copied':copied,'before':before,'after':after,'exit_code':result.returncode,
                         'marker':(base/'data/migration_complete.json').exists(),
                         'scope':'Real Rust SqliteStore open/migrations only; full Manager startup intentionally not used on copied user queue.'})
        # Separate disposable installation for actual updater; real DB copy never enters runtime.
        upgrade=root/'upgrade';(upgrade/'data').mkdir(parents=True);(upgrade/'engine').mkdir()
        (upgrade/'AfuDM.exe').write_bytes(b'T2-legacy-2.9.8-placeholder')
        (upgrade/'engine/user-extra.bin').write_bytes(b'preserve-user-engine')
        (upgrade/'data/keep.txt').write_text('preserve-user-data')
        serve=root/'serve';serve.mkdir();zpath=serve/'AfuDM-v3.0.0-win64.zip'
        exe=ROOT/'app/target/debug/AfuDM.exe';want=digest_file(exe)
        with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED) as z:
            z.write(exe,'AfuDM/AfuDM.exe')
            z.write(SOURCE/'engine/aria2c.exe','AfuDM/engine/aria2c.exe')
            for ui in (ROOT/'app/ui').rglob('*'):
                if ui.is_file():z.write(ui,'AfuDM/ui/'+ui.relative_to(ROOT/'app/ui').as_posix())
        (serve/(zpath.name+'.sha256')).write_text(digest_file(zpath)+'  '+zpath.name)
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self,*a,**kw):super().__init__(*a,directory=str(serve),**kw)
            def log_message(self,*a):pass
        srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=srv.serve_forever,daemon=True).start()
        url=f'http://127.0.0.1:{srv.server_port}'
        release={'tag_name':'v3.0.0','draft':False,'prerelease':False,'body':'T2 local update',
                 'assets':[{'name':n,'browser_download_url':url+'/'+n} for n in (zpath.name,zpath.name+'.sha256')]}
        (serve/'latest').write_text(json.dumps(release))
        helper=root/'update_helper.py';helper.write_text(HELPER,encoding='utf-8')
        api={}
        try:
            proc=subprocess.run([sys.executable,'-B',str(helper),str(SOURCE),str(upgrade),url+'/latest'],cwd=root,
                                capture_output=True,timeout=60,**HIDDEN)
            api=json.loads((upgrade/'update_api_result.json').read_text()) if (upgrade/'update_api_result.json').exists() else {}
            deadline=time.monotonic()+30
            while time.monotonic()<deadline and not (upgrade/'launch_captured.txt').exists():time.sleep(.2)
            replaced=digest_file(upgrade/'AfuDM.exe')==want
            extra=(upgrade/'engine/user-extra.bin').read_bytes()==b'preserve-user-engine'
            data=(upgrade/'data/keep.txt').read_text()=='preserve-user-data'
            ok=proc.returncode==0 and api.get('download',{}).get('ok') and api.get('ready') and api.get('apply',{}).get('kapat') and replaced and extra and data
            emit('updater',{'status':'GECTI' if ok else 'KALDI','api':api,'helper_exit':proc.returncode,
                            'helper_stderr':proc.stderr.decode(errors='replace')[-1000:],
                            'exe_replaced_sha256':want if replaced else None,'extra_engine_preserved':extra,'data_preserved':data,
                            'relaunch_captured':(upgrade/'launch_captured.txt').exists(),
                            'adaptations':['SURUM=2.9.8 in isolated helper (available source reports 2.9.6)',
                            'IZINLI_ONEK=loopback fake GitHub only','Final PowerShell Start-Process intercepted to prevent any application/window launch; copy/backup script executed unchanged.']})
        finally:
            srv.shutdown();srv.server_close()
            # Wait for each exact updater child PID before allowing temp cleanup.
            owned=[]
            for pid in api.get('launcher_pids',[]):
                try:owned.append(psutil.Process(pid))
                except psutil.Error:pass
            _,alive=psutil.wait_procs(owned,timeout=10)
            for p in alive:
                try:p.kill()
                except psutil.Error:pass
        print('MIGRATION',json.loads((OUT/'migration.json').read_text())['status'])
        print('UPDATER',json.loads((OUT/'updater.json').read_text())['status'])
        return 0 if ok and migration_ok else 1
if __name__=='__main__':sys.exit(main())
