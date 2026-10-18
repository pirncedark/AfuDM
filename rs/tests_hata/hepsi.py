"""python tests_hata/hepsi.py: scenarios 1,2,4,5; isolated, headless, offline."""
import argparse, json, sys, tempfile, traceback, time
from common import *
from scenarios import resource, fuzz, bridge, network, crash

def main():
    p=argparse.ArgumentParser();p.add_argument('--only',choices=['resources','fuzz','bridge','network','crash','smoke'])
    p.add_argument('--idle-seconds',type=int,default=300);args=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='afudm_t2_') as tmp:
        apps=[];taze=[];server=FileServer();errors=[]
        selected=[] if args.only=='smoke' else [args.only] if args.only else ['resources','fuzz','crash','bridge','network']
        for name in selected:
            (OUT/(name+'.json')).unlink(missing_ok=True)
        (OUT/'runner_errors.json').unlink(missing_ok=True)
        emit('runner_progress',{'status':'RUNNING','selected':selected,'completed':[]})
        completed=[]
        try:
            for side in ('rs',):
                a=App(side,tmp);apps.append(a);a.start()
                print(f'READY {side} API={a.port} gate={a.gate} isolated data',flush=True)
            if args.only=='smoke':
                for a in apps:print(a.kind,a.call('surum_bilgi',[]),a.http('/ping'),flush=True)
                return 0
            def fresh(fn):
                # fuzz/bridge/network: Each phase starts with fresh isolated Rust data; crash uses the main instance.
                def run():
                    sub=tempfile.mkdtemp(prefix='fresh_',dir=tmp);pair=[]
                    try:
                        for side in ('rs',):
                            a=App(side,sub);taze.append(a);pair.append(a);a.start()
                            print(f'READY {side} API={a.port} gate={a.gate} fresh data',flush=True)
                        return fn(pair)
                    finally:
                        for a in pair:a.close()
                return run
            phases={'resources':lambda:resource(apps,server,args.idle_seconds),'fuzz':fresh(lambda p:fuzz(p,server)),
                    'crash':lambda:crash(apps,server),'bridge':fresh(lambda p:bridge(p,server)),'network':fresh(lambda p:network(p))}
            for name,fn in phases.items():
                if args.only and args.only!=name:continue
                print('START',name,flush=True)
                try:fn()
                except Exception as e:
                    errors.append({'phase':name,'error':str(e),'traceback':traceback.format_exc()})
                    emit('runner_errors',errors);print(traceback.format_exc(),flush=True)
                completed.append(name)
                emit('runner_progress',{'status':'RUNNING','selected':selected,'completed':completed})
                print('END',name,flush=True)
        finally:
            server.shutdown();server.server_close()
            for a in apps+taze:
                try:a.close()
                except Exception as e:print("Cleanup failure:",a.kind,type(e).__name__,flush=True)
            alive=[p.pid for a in apps+taze for p in a.owned()]
            emit('cleanup',{'all_owned_processes_stopped':not alive,'remaining':alive})
            print('CLEANUP all owned processes stopped:',not alive,flush=True)
    checks=[]
    for name in ('resources','fuzz','crash','bridge','network'):
        if args.only and args.only!=name:continue
        f=OUT/(name+'.json')
        if not f.exists():checks.append(False);continue
        v=json.loads(f.read_text(encoding='utf-8'))
        # Every retained Rust crash check must pass.
        if name=='crash':ok=all(x.get('status')=='GECTI' for x in v if x.get('side')=='rs')
        else:ok=all(x.get('status')=='GECTI' for x in v) if isinstance(v,list) else v.get('status')=='GECTI'
        checks.append(ok);print('RESULT',name,'GECTI' if ok else 'KALDI',flush=True)
    code=int(bool(errors) or bool(alive) or not all(checks))
    emit('runner_progress',{'status':'FINISHED','selected':selected,'completed':completed,'exit_code':code})
    return code
if __name__=='__main__':sys.exit(main())
