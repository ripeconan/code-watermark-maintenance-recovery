"""Supplement original development replays without overwriting their evidence."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse,concurrent.futures,gzip,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def worker(job):
    from replay_pilot import init
    init()
    from structural_recovery import score_code
    from measure_exposure import inspect
    from fine_replay import merge
    r=job['record'];codes=job['codes'];start=time.time()
    out={k:r[k] for k in ('id','repo','language','split','sha','parent_sha','filename','key','stratum')}
    out['original_merge_status']=r['merge_status'];out['embedding']=r['embedding']
    merged,info=merge(codes['negative_before'],codes['positive_before'],codes['negative_after'])
    out.update(replay_detail=info,merge_status='clean' if merged is not None else 'conflict')
    if merged is not None:
        old=r['group_scores']['positive_before'];after=score_code(merged,r['language'],job['key_bytes'],old['context'],max_radius=4)
        out.update(detection=after,marked_context_changed=old['context']!=after['context'],
            old_context_in_syntax=old['context'] in after.get('syntax_candidates',[]),
            code_sha256=hashlib.sha256(merged.encode()).hexdigest(),code=merged,
            agrees_with_git=(merged==codes['positive_after']) if 'positive_after' in codes else None)
        _,b=inspect(codes['positive_before'],r['language']);_,a=inspect(merged,r['language'])
        if a is not None and b is not None:
            shared=set(a)&set(b);out['grade_audit']=dict(before=len(b),after=len(a),shared=len(shared),unchanged_shared_votes=sum(a[h]==b[h] for h in shared))
    out['seconds']=time.time()-start
    return out

def isolated(job):
    try:
        p=subprocess.run([sys.executable,__file__,'--worker'],input=json.dumps(job),capture_output=True,text=True,timeout=180)
        if p.returncode:raise RuntimeError(f'exit {p.returncode}: '+p.stderr[-1200:])
        return json.loads(p.stdout)
    except Exception as e:return {k:job['record'][k] for k in ('id','key','repo','stratum')}|dict(error=type(e).__name__+': '+str(e))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--worker',action='store_true');a=ap.parse_args()
    if a.worker:
        j=json.load(sys.stdin);j['key_bytes']=bytes(j['key_bytes']);print(json.dumps(worker(j)));return
    from fine_replay import self_check
    self_check()
    out=ROOT/'results/refined_replay_pilot.jsonl';dest=ROOT/'data/refined_codes';dest.mkdir(parents=True,exist_ok=True)
    done={(r['id'],r['key']) for s in out.read_text().splitlines() if s and (r:=json.loads(s))} if out.exists() else set()
    rows=[json.loads(s) for s in (ROOT/'results/replay_pilot.jsonl').read_text().splitlines() if s]
    jobs=[]
    for r in rows:
        if 'codes_file' not in r or (r['id'],r['key']) in done:continue
        codes=json.loads(gzip.decompress((ROOT/r['codes_file']).read_bytes()))
        if 'positive_before' not in codes:continue
        jobs.append(dict(record=r,codes=codes,key_bytes=list(hashlib.sha256(('confirmation20261028|'+str(r['key'])).encode()).digest())))
    started=time.time()
    with out.open('a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        for i,r in enumerate(ex.map(isolated,jobs),1):
            code=r.pop('code',None)
            if code is not None:
                cp=dest/f"{r['id']}_{r['key']}.txt.gz";cp.write_bytes(gzip.compress(code.encode(),mtime=0));r['code_file']=str(cp.relative_to(ROOT))
            f.write(json.dumps(r)+'\n');f.flush()
            if i%12==0:print('FINE_REPLAY',i,len(jobs),round(time.time()-started,1),flush=True)
    print('FINE_REPLAY_DONE',len(jobs),round(time.time()-started,1),flush=True)

if __name__=='__main__':main()
