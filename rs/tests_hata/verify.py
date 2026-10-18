"""Build/check exact cargo exit codes and preserve raw output (no PowerShell wrapping)."""
import json, subprocess, shutil
from common import *

def main():
    commands=[('build_feature',['cargo','build','--manifest-path','app/Cargo.toml','--features','test-kapisi','--offline']),
              ('test_feature',['cargo','test','--manifest-path','app/Cargo.toml','--features','test-kapisi','--offline']),
              ('clippy_feature',['cargo','clippy','--manifest-path','app/Cargo.toml','--features','test-kapisi','--offline','--','-D','warnings']),
              ('build_default',['cargo','build','--manifest-path','app/Cargo.toml','--offline']),
              ('test_default',['cargo','test','--manifest-path','app/Cargo.toml','--offline']),
              ('clippy_default',['cargo','clippy','--manifest-path','app/Cargo.toml','--offline','--','-D','warnings']),
              ('format_owned',['rustfmt','--edition','2021','--check','--config','skip_children=true','app/src/main.rs','app/src/test_kapisi.rs'])]
    rows=[]
    for name,cmd in commands:
        with open(OUT/(name+'.log'),'wb') as log:r=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,**HIDDEN)
        row={'name':name,'command':cmd,'exit_code':r.returncode};rows.append(row)
        if name=='build_feature' and r.returncode==0:
            dest=ROOT/'tests_hata/bin';dest.mkdir(exist_ok=True)
            shutil.copy2(ROOT/'app/target/debug/AfuDM.exe',dest/'AfuDM_test.exe')
            row['gate_path_in_binary']=b'/_test/api_call' in (dest/'AfuDM_test.exe').read_bytes()
        if name=='build_default' and r.returncode==0:
            row['gate_path_in_binary']=b'/_test/api_call' in (ROOT/'app/target/debug/AfuDM.exe').read_bytes()
        emit('verification',rows)
        print(name,r.returncode,flush=True)
    return int(any(r['exit_code'] for r in rows))
if __name__=='__main__':sys.exit(main())
