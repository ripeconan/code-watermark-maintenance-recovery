"""One native discovery/detection call per process; three independent repetitions."""
import concurrent.futures,hashlib,json,os,random,statistics,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def one(path):
    from recovery_probe import init
    init(json.loads((ROOT/'records/tool_paths.json').read_text())['vendor'])
    from recovery_detector import detect_recovery
    j=json.loads(Path(path).read_text());key=hashlib.sha256(('confirmation20261028|'+str(j['key'])).encode()).digest()
    ds=json.loads((ROOT/'records/context_delta_dictionary.json').read_text())['deltas'][j['language']]
    s=detect_recovery(j['variant']['code'],j['language'],key,j['method'],deltas=ds);e=j['variant']['detection']
    assert abs(s['min_p']-e['scores'].get(j['method'],1.))<1e-12
    assert s['candidates']==e['candidates'].get(j['method'],0)
    print(json.dumps(s))

def run(j):
    env=dict(os.environ,PYTHONMALLOC='debug',PYTHONFAULTHANDLER='1',PYTHONPATH=str(ROOT/'tools/python'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    py='/home2/icdm/crosslingual-codewatermark/upgrade_probe_20261019/.venv/bin/python'
    with tempfile.TemporaryDirectory(prefix='cwm-single-timing-') as td:
        p=Path(td)/'input.json';p.write_text(json.dumps(j))
        r=subprocess.run([py,'-u',str(Path(__file__).resolve()),str(p)],capture_output=True,text=True,env=env,timeout=120)
    return dict(**{k:j[k] for k in ('id','language','edit','method','repeat')},returncode=r.returncode,stderr=r.stderr[-6000:],result=json.loads(r.stdout) if r.returncode==0 else None)

def main():
    records=list(map(json.loads,(ROOT/'results/confirmation_extended.jsonl').read_text().splitlines()));jobs=[]
    for lang in ('python','java','cpp'):
        rows=[r for r in records if r['language']==lang and r['split']=='valid' and r['key']==15485863]
        rows.sort(key=lambda r:hashlib.sha256(('timing|'+r['id']).encode()).hexdigest())
        for r in rows[:16]:
            for edit in ('original','helper','formatter_helper','helper_loop'):
                v=r['groups']['positive']['variants'].get(edit)
                if not v:continue
                methods=['official','syntax','nearest_budget','l1_1','l1_2','l1_3','l1_4','delta_dictionary']
                random.Random(lang+'|'+r['id']+'|'+edit).shuffle(methods)
                for rep in range(3):jobs.extend(dict(id=r['id'],language=lang,key=r['key'],edit=edit,method=m,repeat=rep,variant=v) for m in methods)
    out=[];start=time.time()
    with (ROOT/'records/timing_single_call_checks.jsonl').open('w') as log,concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for i,r in enumerate(ex.map(run,jobs),1):
            log.write(json.dumps(r)+'\n');log.flush()
            if r['returncode']:raise RuntimeError(r)
            out.append(r)
            if i%300==0:print('TIMING',i,len(jobs),round(time.time()-start,1),flush=True)
    grouped={}
    for r in out:grouped.setdefault(tuple(r[k] for k in ('id','language','edit','method')),[]).append(r['result'])
    rows=[]
    for keys,rr in grouped.items():
        times=[x['seconds'] for x in rr];assert len(times)==3
        rows.append(dict(zip(('id','language','edit','method'),keys),candidates=rr[0]['candidates'],grades=rr[0]['grades'],median_seconds=statistics.median(times),repeats=times))
    summary=dict(rows=rows,parity_cases=len(out),budget_mismatches=[],isolated_processes=len(out),process_startup_excluded=True,concurrent_timing_workers=4,
        protocol='Exactly one detection call in each fresh debug-allocator process; three repetitions per fixed method/code. Failed earlier timing runs retained separately.')
    (ROOT/'results/recovery_timing.json').write_text(json.dumps(summary,indent=2));print('TIMING_VERIFIED',len(out),flush=True)

if __name__=='__main__':one(sys.argv[1]) if len(sys.argv)>1 else main()
