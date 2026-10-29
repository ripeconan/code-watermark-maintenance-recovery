"""Single-code fresh-process timing/parity, avoiding long-lived native parser state."""
import concurrent.futures,hashlib,json,os,random,statistics,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def one(path):
    from recovery_probe import init
    init(json.loads((ROOT/'records/tool_paths.json').read_text())['vendor'])
    from recovery_detector import detect_recovery
    j=json.loads(Path(path).read_text());key=hashlib.sha256(('confirmation20261028|'+str(j['key'])).encode()).digest()
    ds=json.loads((ROOT/'records/context_delta_dictionary.json').read_text())['deltas'][j['language']]
    methods=[j['method']];out=[]
    for method in methods:
        ts=[]
        for _ in range(3):
            s=detect_recovery(j['variant']['code'],j['language'],key,method,deltas=ds);expected=j['variant']['detection']
            assert abs(s['min_p']-expected['scores'].get(method,1.))<1e-12,(j['id'],method,'score')
            assert s['candidates']==expected['candidates'].get(method,0),(j['id'],method,'count')
            ts.append(s['seconds'])
        out.append(dict(id=j['id'],language=j['language'],edit=j['edit'],method=method,candidates=s['candidates'],grades=s['grades'],median_seconds=statistics.median(ts),repeats=ts))
    print(json.dumps(out))

def run(j):
    env=dict(os.environ,PYTHONMALLOC='debug',PYTHONFAULTHANDLER='1',PYTHONPATH=str(ROOT/'tools/python'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    py='/home2/icdm/crosslingual-codewatermark/upgrade_probe_20261019/.venv/bin/python'
    with tempfile.TemporaryDirectory(prefix='cwm-isolated-timing-') as td:
        p=Path(td)/'input.json';p.write_text(json.dumps(j))
        r=subprocess.run([py,'-u',str(Path(__file__).resolve()),str(p)],capture_output=True,text=True,env=env,timeout=120)
    return dict(id=j['id'],language=j['language'],edit=j['edit'],method=j['method'],returncode=r.returncode,stderr=r.stderr[-6000:],rows=json.loads(r.stdout) if r.returncode==0 else [])

def main():
    records=list(map(json.loads,(ROOT/'results/confirmation_extended.jsonl').read_text().splitlines()));jobs=[];mismatches=[]
    for r in records:
        for g in r['groups'].values():
            for v in g['variants'].values():
                c=v['detection']['candidates']
                if c.get('syntax')!=c.get('nearest_budget'):mismatches.append((r['id'],r['language']))
    for lang in ('python','java','cpp'):
        rows=[r for r in records if r['language']==lang and r['split']=='valid' and r['key']==15485863]
        rows.sort(key=lambda r:hashlib.sha256(('timing|'+r['id']).encode()).hexdigest())
        for r in rows[:16]:
            for edit in ('original','helper','formatter_helper','helper_loop'):
                v=r['groups']['positive']['variants'].get(edit)
                if v:
                    methods=['official','syntax','nearest_budget','l1_1','l1_2','l1_3','l1_4','delta_dictionary']
                    random.Random(lang+'|'+r['id']+'|'+edit).shuffle(methods)
                    jobs.extend(dict(id=r['id'],language=lang,key=r['key'],edit=edit,method=m,variant=v) for m in methods)
    out=[];start=time.time()
    with (ROOT/'records/timing_method_isolated_checks.jsonl').open('w') as log,concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        for i,r in enumerate(ex.map(run,jobs),1):
            rows=r.pop('rows');log.write(json.dumps(r)+'\n');log.flush()
            if r['returncode']:raise RuntimeError(r)
            out+=rows
            if i%120==0:print('TIMING',i,len(jobs),round(time.time()-start,1),flush=True)
    summary=dict(rows=out,parity_cases=3*len(out),budget_mismatches=mismatches,isolated_processes=len(jobs),process_startup_excluded=True,concurrent_timing_workers=2)
    (ROOT/'results/recovery_timing.json').write_text(json.dumps(summary,indent=2));print('TIMING_VERIFIED',summary['parity_cases'],flush=True)

if __name__=='__main__':one(sys.argv[1]) if len(sys.argv)>1 else main()
