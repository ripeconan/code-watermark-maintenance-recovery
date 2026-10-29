"""Read-only structural census. All invocations must run on inner."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse,collections,concurrent.futures,gzip,hashlib,json,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def init():
    paths=json.loads((ROOT/'records/tool_paths.json').read_text())
    sys.path.insert(0,paths['baseline_scripts']);sys.path.insert(0,paths['vendor'])

def inspect(code,language):
    from sew.sites.discovery import discover
    from sew.sites.ctx import context
    from structural_recovery import syntax_candidates
    tree,_,recs=discover(code,language)
    if tree is None:return dict(parse_ok=False,grades=0),None
    raw=tuple(map(int,context(tree,language)[0][4:].split('.')))
    observed=tuple(map(int,recs[0].sid[-1][4:].split('.'))) if recs else raw
    groups=collections.defaultdict(list)
    for r in recs:groups[r.sid[:-1]].append(r.value)
    votes={h:int(2*sum(v)>=len(v)) for h,v in groups.items()}
    cand=syntax_candidates(tree,observed,language)
    return dict(parse_ok=True,grades=len(groups),sites=len(recs),context=observed,raw_context=raw,
        canonicalized_context=observed!=raw,syntax_candidates=[list(c) for c in sorted(cand)]),votes

def work(row):
    init();start=time.time()
    r={k:v for k,v in row.items() if k not in ('before','after')}
    before,bvotes=inspect(row['before'],row['language']);after,avotes=inspect(row['after'],row['language'])
    r.update(before=before,after=after,seconds=time.time()-start)
    if before['parse_ok'] and after['parse_ok']:
        delta=[b-a for a,b in zip(before['context'],after['context'])]
        common=set(bvotes)&set(avotes)
        r.update(delta=delta,context_changed=any(delta),delta_l1=sum(map(abs,delta)),
            delta_sign=('zero' if not any(delta) else 'nonnegative' if min(delta)>=0 else 'nonpositive' if max(delta)<=0 else 'mixed'),
            original_in_syntax=list(before['context']) in after['syntax_candidates'],
            shared_heads=len(common),retained_votes=sum(bvotes[h]==avotes[h] for h in common),
            changed_votes=sum(bvotes[h]!=avotes[h] for h in common),
            lost_heads=len(set(bvotes)-set(avotes)),new_heads=len(set(avotes)-set(bvotes)))
    return r

def isolated(row):
    t=time.time()
    try:
        p=subprocess.run([sys.executable,__file__,'--worker'],input=json.dumps(row),capture_output=True,text=True,timeout=90)
        if p.returncode:raise RuntimeError(f'exit {p.returncode}: '+p.stderr[-1200:])
        return json.loads(p.stdout)
    except Exception as e:return {k:v for k,v in row.items() if k not in ('before','after')}|dict(error=type(e).__name__+': '+str(e),seconds=time.time()-t)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--worker',action='store_true');ap.add_argument('--workers',type=int,default=2);a=ap.parse_args()
    if a.worker:
        print(json.dumps(work(json.load(sys.stdin))));return
    init();rows=[]
    for p in sorted((ROOT/'data/pairs').glob('*.json.gz')):rows.extend(json.loads(gzip.decompress(p.read_bytes())))
    out=ROOT/'results/exposure.jsonl';out.parent.mkdir(parents=True,exist_ok=True)
    done={json.loads(s)['id'] for s in out.read_text().splitlines() if s} if out.exists() else set()
    pending=[r for r in rows if r['id'] not in done];start=time.time()
    with out.open('a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i,r in enumerate(ex.map(isolated,pending),1):
            f.write(json.dumps(r)+'\n');f.flush()
            if i%20==0:print('EXPOSURE',i,len(pending),'seconds',round(time.time()-start,1),flush=True)
    records=[json.loads(s) for s in out.read_text().splitlines() if s];summary=[]
    for repo in sorted({r['repo'] for r in records}):
        rr=[r for r in records if r['repo']==repo];valid=[r for r in rr if 'context_changed' in r];changed=[r for r in valid if r['context_changed']]
        summary.append(dict(repo=repo,language=rr[0]['language'],split=rr[0]['split'],sampled=len(rr),
            commits=len({r['sha'] for r in rr}),both_parse=len(valid),context_changed=len(changed),
            syntax_covers_changed=sum(r['original_in_syntax'] for r in changed),
            sign=dict(collections.Counter(r['delta_sign'] for r in valid)),
            errors=sum('error' in r for r in rr),
            over_256_grades=sum(max(r['before']['grades'],r['after']['grades'])>256 for r in valid)))
    (ROOT/'results/exposure_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
