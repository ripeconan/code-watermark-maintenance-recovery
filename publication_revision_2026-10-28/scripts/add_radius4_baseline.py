"""Stronger generic search reaches the excluded loop-helper's L1 delta four.

Supplementary baseline added after initial outcomes; candidate rule and primary
method unchanged. Every row runs in a fresh debug-allocator process.
"""
import concurrent.futures,hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def one(path):
    from recovery_probe import init
    init(json.loads((ROOT/'records/tool_paths.json').read_text())['vendor'])
    from recovery_detector import detect_recovery
    r=json.loads(Path(path).read_text());key=hashlib.sha256(('confirmation20261028|'+str(r['key'])).encode()).digest()
    for g in r['groups'].values():
        for v in g['variants'].values():
            s=detect_recovery(v['code'],r['language'],key,'l1_4');d=v['detection']
            d['scores']['l1_4']=s['min_p'];d['candidates']['l1_4']=s['candidates']
    print(json.dumps(r))

def run(r):
    env=dict(os.environ,PYTHONMALLOC='debug',PYTHONFAULTHANDLER='1',PYTHONPATH=str(ROOT/'tools/python'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    py='/home2/icdm/crosslingual-codewatermark/upgrade_probe_20261019/.venv/bin/python'
    with tempfile.TemporaryDirectory(prefix='cwm-radius4-') as td:
        f=Path(td)/'row.json';f.write_text(json.dumps(r))
        p=subprocess.run([py,'-u',str(Path(__file__).resolve()),str(f)],capture_output=True,text=True,env=env,timeout=120)
        if p.returncode:raise RuntimeError((r['id'],r['language'],r['key'],p.stderr[-5000:]))
        return json.loads(p.stdout)

def main():
    for stem in ('confirmation','structural_stress'):
        source=ROOT/'results'/('confirmation_augmented.jsonl' if stem=='confirmation' else 'structural_stress.jsonl')
        rows=list(map(json.loads,source.read_text().splitlines()));start=time.time()
        with (ROOT/'results'/(stem+'_extended.jsonl')).open('w') as f,concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            for i,r in enumerate(ex.map(run,rows),1):
                f.write(json.dumps(r)+'\n');f.flush()
                if i%100==0:print(stem,i,len(rows),round(time.time()-start,1),flush=True)
        print('EXTENDED_DONE',stem,len(rows),flush=True)

if __name__=='__main__':one(sys.argv[1]) if len(sys.argv)>1 else main()
