"""Fresh debug-allocator replication of dictionary, development and patch results."""
import concurrent.futures,gzip,json,os,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def differences(a,b,path=''):
    if isinstance(a,dict) and isinstance(b,dict):
        out=[]
        for k in set(a)|set(b):
            if k=='seconds':continue
            if k not in a or k not in b:out.append(path+'/'+k)
            else:out.extend(differences(a[k],b[k],path+'/'+k))
        return out
    if isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):
        if len(a)!=len(b):return [path+'/length']
        return [p for i,(x,y) in enumerate(zip(a,b)) for p in differences(x,y,path+'/'+str(i))]
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):
        return [] if abs(a-b)<=1e-12 else [path]
    return [] if a==b else [path]

def one(path):
    j=json.loads(Path(path).read_text());paths=json.loads((ROOT/'records/tool_paths.json').read_text())
    if j['kind']=='dictionary':
        from add_delta_dictionary_baseline import init,work
        ds=json.loads((ROOT/'records/context_delta_dictionary.json').read_text())['deltas'];init(paths['vendor'],ds)
        old=j['input'];new=work(json.loads(json.dumps(old)))
    elif j['kind']=='patch':
        from real_patch_replay import init,work
        init(paths['vendor']);new=work((j['input'],j['key']));old=j['expected']
    else:
        from recovery_probe import init,process
        init(paths['vendor']);new=process(j['input']);old=j['expected']
    diff=differences(old,new)
    print(json.dumps({'differences':diff,'kind':j['kind'],'id':j['id']}))
    return 1 if diff else 0

def run(job):
    env=dict(os.environ,PYTHONMALLOC='debug',PYTHONFAULTHANDLER='1',PYTHONPATH=str(ROOT/'tools/python'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    py='/home2/icdm/crosslingual-codewatermark/upgrade_probe_20261019/.venv/bin/python'
    with tempfile.TemporaryDirectory(prefix='cwm-additional-audit-') as td:
        p=Path(td)/'job.json';p.write_text(json.dumps(job));start=time.time()
        try:
            r=subprocess.run([py,'-u',str(Path(__file__).resolve()),str(p)],capture_output=True,text=True,env=env,timeout=120)
            try:detail=json.loads(r.stdout)
            except ValueError:detail={'stdout':r.stdout[-3000:]}
            return dict(kind=job['kind'],id=job['id'],returncode=r.returncode,detail=detail,stderr=r.stderr[-6000:],seconds=time.time()-start)
        except subprocess.TimeoutExpired:return dict(kind=job['kind'],id=job['id'],returncode='timeout')

def main():
    jobs=[]
    sources=json.loads(gzip.decompress((ROOT/'data/real_patch_sources.json.gz').read_bytes()))
    sm={(s['repo'],s['sha'],s['filename']):s for s in sources}
    for r in map(json.loads,(ROOT/'results/real_patch_replay.jsonl').read_text().splitlines()):
        jobs.append(dict(kind='patch',id='|'.join(str(r[k]) for k in ('repo','sha','filename','key')),key=r['key'],input=sm[r['repo'],r['sha'],r['filename']],expected=r))
    for r in map(json.loads,(ROOT/'results/confirmation_augmented.jsonl').read_text().splitlines()):
        jobs.append(dict(kind='dictionary',id=f"{r['language']}|{r['id']}|{r['key']}",input=r))
    old={}
    for r in map(json.loads,(ROOT/'results/recovery_exploratory.jsonl').read_text().splitlines()):
        old.setdefault((r['model'],r['task_id'],r['key']),[]).append(r)
    for r in map(json.loads,Path('/home2/icdm/crosslingual-codewatermark/major_revision_20261027/sew_generated_v2.jsonl').read_text().splitlines()):
        if r['mode']=='official':jobs.append(dict(kind='development',id=f"{r['model']}|{r['task_id']}|{r['key']}",input=r,expected=old[r['model'],r['task_id'],r['key']]))
    dest=ROOT/'records/additional_isolated_checks.jsonl';done=set()
    if dest.exists():
        for r in map(json.loads,dest.read_text().splitlines()):done.add((r['kind'],r['id']))
    jobs=[j for j in jobs if (j['kind'],j['id']) not in done];start=time.time()
    with dest.open('a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        for i,r in enumerate(ex.map(run,jobs),1):
            f.write(json.dumps(r)+'\n');f.flush()
            if r['returncode']!=0:print('FAIL',r['kind'],r['id'],r['returncode'],flush=True)
            if i%100==0:print('AUDITED',i,len(jobs),round(time.time()-start,1),flush=True)
    rows=list(map(json.loads,dest.read_text().splitlines()));summary={}
    for kind in ('patch','dictionary','development'):
        selected=[r for r in rows if r['kind']==kind];summary[kind]=dict(cases=len(selected),failures=sum(r['returncode']!=0 for r in selected))
    (ROOT/'records/additional_isolated_summary.json').write_text(json.dumps(summary,indent=2));print('DONE',summary,flush=True)
    return int(any(r['returncode']!=0 for r in rows))

if __name__=='__main__':sys.exit(one(sys.argv[1]) if len(sys.argv)>1 else main())
