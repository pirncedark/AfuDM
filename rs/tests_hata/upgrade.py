"""Scenario 3: Rust migration of an explicitly supplied offline database copy."""
import argparse, hashlib, http.server, json, os, shutil, sqlite3, subprocess, sys, tempfile, threading, time, zipfile
from common import *
from contextlib import closing

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
    parser=argparse.ArgumentParser()
    parser.add_argument('--snapshot-dir',type=Path,required=True,help='Offline DB/WAL/SHM snapshot directory')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args()
    if args.output_dir:
        import common
        globals()['OUT']=common.OUT=args.output_dir.resolve()
        OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='afudm_t2_update_') as tmp:
        root=Path(tmp);base=root/'install';(base/'data').mkdir(parents=True)
        oldexe=base/'AfuDM.exe';oldexe.write_bytes(b'T2-legacy-2.9.8-installation-placeholder')
        # Physical copies only: no SQLite connection to the live database.
        copied=[]
        for name in ('afudm.db','afudm.db-wal','afudm.db-shm'):
            src=args.snapshot_dir/name
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
        print('MIGRATION', 'GECTI' if migration_ok else 'KALDI', flush=True)
        return 0 if migration_ok else 1
if __name__=='__main__':sys.exit(main())
