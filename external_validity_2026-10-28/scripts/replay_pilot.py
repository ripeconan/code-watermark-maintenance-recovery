"""Fresh-process real-patch replay; development data only until method freeze."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse,collections,concurrent.futures,gzip,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
KEYS=(15485863,32452843,49979687)

def init():
    p=json.loads((ROOT/'records/tool_paths.json').read_text())
    sys.path.insert(0,p['baseline_scripts']);sys.path.insert(0,p['vendor'])
    import recovery_probe
    recovery_probe.init(p['vendor'])

def work(job):
    init()
    from sew.embed import embed
    from structural_recovery import score_code
    from measure_exposure import inspect
    row,key_id=job['row'],job['key'];lang=row['language'];start=time.time()
    key=hashlib.sha256(('confirmation20261028|'+str(key_id)).encode()).digest()
    r={k:v for k,v in row.items() if k not in ('before','after')}
    r.update(key=key_id,stratum=job['stratum'],group_scores={},merge_status='not_attempted',functional_status='not_tested')
    codes=dict(negative_before=row['before'],negative_after=row['after'])
    binfo,_=inspect(row['before'],lang);ainfo,_=inspect(row['after'],lang)
    if max(binfo['grades'],ainfo['grades'])>256:
        r.update(resource_abstention='over_256_grades',source_grades=[binfo['grades'],ainfo['grades']]);return r
    for group,code in codes.items():r['group_scores'][group]=score_code(code,lang,key,max_radius=4)
    em=embed(row['before'],lang,key);marked=em.pop('code');r['embedding']=em;codes['positive_before']=marked
    before=score_code(marked,lang,key,max_radius=4);r['group_scores']['positive_before']=before
    with tempfile.TemporaryDirectory(prefix='cwm-maintenance-') as td:
        fs=[Path(td)/s for s in ('marked','base','revised')]
        for p,code in zip(fs,(marked,row['before'],row['after'])):p.write_bytes(code.encode())
        merge=subprocess.run(['git','merge-file','-p',*map(str,fs)],capture_output=True,timeout=30)
    r.update(merge_returncode=merge.returncode,merge_stderr=merge.stderr.decode('utf8','replace')[-1000:],
        merge_status='clean' if merge.returncode==0 else 'conflict' if merge.returncode>0 else 'error')
    if merge.returncode==0:
        codes['positive_after']=merge.stdout.decode('utf8')
        after=score_code(codes['positive_after'],lang,key,before['context'],max_radius=4)
        r['group_scores']['positive_after']=after
        _,votes_before=inspect(marked,lang);_,votes_after=inspect(codes['positive_after'],lang)
        if votes_before is not None and votes_after is not None:
            shared=set(votes_before)&set(votes_after)
            r['grade_audit']=dict(before=len(votes_before),after=len(votes_after),shared=len(shared),
                unchanged_shared_votes=sum(votes_before[h]==votes_after[h] for h in shared))
        r['old_context_in_syntax']=before['context'] in after.get('syntax_candidates',[])
        r['marked_context_changed']=before['context']!=after['context']
    r.update(codes=codes,seconds=time.time()-start)
    return r

def isolated(job):
    start=time.time()
    try:
        p=subprocess.run([sys.executable,__file__,'--worker'],input=json.dumps(job),capture_output=True,text=True,timeout=180)
        if p.returncode:raise RuntimeError(f'exit {p.returncode}: '+p.stderr[-1500:])
        return json.loads(p.stdout)
    except Exception as e:
        return {k:v for k,v in job['row'].items() if k not in ('before','after')}|dict(key=job['key'],stratum=job['stratum'],error=type(e).__name__+': '+str(e),seconds=time.time()-start)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--worker',action='store_true');ap.add_argument('--workers',type=int,default=2);a=ap.parse_args()
    if a.worker:
        print(json.dumps(work(json.load(sys.stdin))));return
    exposure={r['id']:r for s in (ROOT/'results/exposure.jsonl').read_text().splitlines() if s and (r:=json.loads(s))['split']=='development'}
    sources=[]
    for p in sorted((ROOT/'data/pairs').glob('*.json.gz')):sources.extend(r for r in json.loads(gzip.decompress(p.read_bytes())) if r['split']=='development')
    chosen=[]
    for repo in sorted({r['repo'] for r in sources}):
        for changed in (False,True):
            rows=[r for r in sources if r['repo']==repo and r['id'] in exposure and exposure[r['id']].get('context_changed') is changed]
            chosen.extend(dict(row=r,stratum='changed' if changed else 'unchanged') for r in sorted(rows,key=lambda r:r['id'])[:12])
    selection=[dict(id=j['row']['id'],repo=j['row']['repo'],sha=j['row']['sha'],filename=j['row']['filename'],stratum=j['stratum']) for j in chosen]
    (ROOT/'records/replay_pilot_selection.json').write_text(json.dumps(selection,indent=2))
    out=ROOT/'results/replay_pilot.jsonl';codes_dir=ROOT/'data/replay_codes';codes_dir.mkdir(parents=True,exist_ok=True)
    done={(r['id'],r['key']) for s in out.read_text().splitlines() if s and (r:=json.loads(s))} if out.exists() else set()
    jobs=[{**j,'key':k} for j in chosen for k in KEYS if (j['row']['id'],k) not in done]
    start=time.time()
    with out.open('a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i,r in enumerate(ex.map(isolated,jobs),1):
            codes=r.pop('codes',None)
            if codes:
                output=codes_dir/f"{r['id']}_{r['key']}.json.gz"
                output.write_bytes(gzip.compress(json.dumps(codes).encode(),mtime=0));r['codes_file']=str(output.relative_to(ROOT))
                r['code_sha256']={g:hashlib.sha256(c.encode()).hexdigest() for g,c in codes.items()}
            f.write(json.dumps(r)+'\n');f.flush()
            if i%12==0:print('REPLAY',i,len(jobs),'seconds',round(time.time()-start,1),flush=True)
    print('REPLAY_DONE',len(jobs),'seconds',round(time.time()-start,1),flush=True)

if __name__=='__main__':main()
