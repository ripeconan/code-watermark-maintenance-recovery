"""Supplementary per-method CPU timing on outcome-independent new-project files."""
import argparse,collections,concurrent.futures,gzip,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
METHODS=('official','syntax','structured64','nearest64','dictionary64','dictionary_pairs64','l1_4')
def worker(job):
    from evaluate_upgrade import init
    init()
    from sew.sites.discovery import discover
    from recovery_probe import grade_score,contexts
    from structural_recovery import syntax_candidates
    from structured_candidates import structured,nearest,dictionary
    key=hashlib.sha256(b'confirmation20261028|15485863').digest();m=job['method'];lang=job['language'];start=time.perf_counter()
    tree,_,recs=discover(job['code'],lang)
    if not recs:return dict(seconds=time.perf_counter()-start,eligible=False,candidates=0)
    c=tuple(map(int,recs[0].sid[-1][4:].split('.')));grades=collections.defaultdict(list)
    for r in recs:grades[r.sid[:-1]].append(r.value)
    if len(grades)>256:return dict(seconds=time.perf_counter()-start,eligible=False,candidates=0)
    if m=='official':cs={c}
    elif m=='syntax':cs=syntax_candidates(tree,c,lang)
    elif m=='structured64':cs=structured(tree,c,lang,64)[0]
    elif m=='nearest64':cs=nearest(c,64)
    elif m=='l1_4':cs=set(contexts(c,4))
    else:cs=dictionary(c,job['dictionary'].get(lang,[]),combinations=m=='dictionary_pairs64')
    score=min(grade_score(grades,d,key,lang) for d in cs)
    return dict(seconds=time.perf_counter()-start,eligible=len(grades)>=5,candidates=len(cs),score=score,grades=len(grades))
def isolated(job):
    meta={k:job[k] for k in ('id','repo','language','method','repeat')}
    try:
        p=subprocess.run([sys.executable,__file__,'--worker'],input=json.dumps(job),capture_output=True,text=True,timeout=120)
        if p.returncode:raise RuntimeError(str(p.returncode)+p.stderr[-500:])
        return meta|json.loads(p.stdout)
    except Exception as e:return meta|dict(error=str(e))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--worker',action='store_true');a=ap.parse_args()
    if a.worker:print(json.dumps(worker(json.load(sys.stdin))));return
    rows=[]
    for p in (ROOT/'data/project_calibration').glob('*.json.gz'):
        if '.frame.' in p.name:continue
        rr=[r for r in json.loads(gzip.decompress(p.read_bytes())) if r['split']=='test']
        rows+=sorted(rr,key=lambda r:hashlib.sha256(('cpu-cost|'+r['id']).encode()).hexdigest())[:8]
    learned=json.loads((ROOT/'records/development_dictionary.json').read_text());jobs=[]
    for r in rows:
        for repeat in range(3):
            for method in METHODS:jobs.append({k:r[k] for k in ('id','repo','language')}|dict(code=r['after'],method=method,repeat=repeat,dictionary=learned))
    import random
    random.Random(2026102807).shuffle(jobs)
    out=ROOT/'results/project_method_timing.jsonl'
    with out.open('w') as f,concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        for i,r in enumerate(ex.map(isolated,jobs),1):
            f.write(json.dumps(r)+'\n');f.flush()
            if i%70==0:print('TIMING',i,len(jobs),flush=True)
    print('TIMING_DONE',len(jobs),flush=True)
if __name__=='__main__':main()
