"""Post-outcome finite-pool sensitivity; frozen full-pool parity precedes draws."""
import argparse, datetime, hashlib, json, math, sys
from pathlib import Path
import numpy as np
from analyze_temporal import available, cutoff
from analyze_upgrade import value

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'robustness_revision_20261029'
METHODS = ('official','syntax','structured64','nearest64','dictionary64','dictionary_pairs64')
KEYS = (15485863,32452843,49979687)
METRICS = ('detection','alarm_lower','alarm_upper','infinite_threshold')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def readrows(p): return [json.loads(s) for s in p.read_text().splitlines() if s]
def encode(x): return float(x) if np.isfinite(x) else str(float(x))
def write(name, x): (OUT/name).write_text(json.dumps(x,indent=2,allow_nan=False))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--parity-only',action='store_true');args=ap.parse_args()
    OUT.mkdir(exist_ok=True)
    data=ROOT/'results/temporal_scores.jsonl'
    assert sha(data)=='316e9de2c2f7e37f532e7e6aa7140d786101887375236f40ef22f55bd17ea2a6'
    rows=readrows(data); assert len(rows)==4125
    summary=json.loads((ROOT/'results/temporal_summary.json').read_text())
    oldt={(x['repo'],x['key'],x['method']):float(x['threshold']) for x in summary['thresholds'] if x['alpha']==.05 and x['mode']=='earlier_paired' and x['method'] in METHODS}
    oldd={(x['repo'],x['id'],x['key'],x['method']):x for x in readrows(ROOT/'results/temporal_decisions.jsonl') if x['alpha']==.05 and x['mode']=='earlier_paired' and x['method'] in METHODS}
    nt=nd=0; prepared={}
    for repo in sorted({r['repo'] for r in rows}):
        rr=[r for r in rows if r['repo']==repo]
        ids=sorted({r['id'] for r in rr if r['split']=='calibration'})
        lookup={(r['id'],r['key']):r for r in rr if r['split']=='calibration'}
        assert len(lookup)==len(ids)*3
        cube=np.empty((len(ids),3,6)); missing=np.empty((len(ids),3),bool)
        tests={}
        for ki,key in enumerate(KEYS):
            for i,uid in enumerate(ids):
                r=lookup[uid,key]; missing[i,ki]=not all(available(r,g) for g in ('negative_before','negative_after'))
                for mi,m in enumerate(METHODS): cube[i,ki,mi]=max(value(r,g,m) if available(r,g) else math.inf for g in ('negative_before','negative_after'))
            tt=sorted((r for r in rr if r['split']=='test' and r['key']==key),key=lambda r:r['id'])
            tests[key]=tt
            for mi,m in enumerate(METHODS):
                threshold,rank=cutoff(cube[:,ki,mi].tolist(),.05)
                assert threshold==oldt[repo,key,m],(repo,key,m,'threshold parity')
                nt+=1
                for r in tt:
                    complete=all(available(r,g) for g in ('negative_before','negative_after'))
                    neg=any(available(r,g) and value(r,g,m)>threshold for g in ('negative_before','negative_after'))
                    emb=r.get('embedding',{}).get('status')=='ok'
                    fields=dict(negative_complete=complete,negative_any=neg,negative_upper=neg or not complete,positive_before=emb and value(r,'positive_before',m)>threshold,positive_after=emb and value(r,'positive_after',m)>threshold,embedding_ok=emb,clean=r.get('merge_status')=='clean')
                    prev=oldd[repo,r['id'],key,m]
                    assert all(prev[k]==v for k,v in fields.items()),(repo,r['id'],key,m,'decision parity')
                    nd+=1
        prepared[repo]=(ids,cube,missing,tests)
    assert nt==108 and nd==12366
    write('p1_parity.json',dict(passed=True,thresholds=nt,decisions=nd,input_sha256=sha(data)))
    if args.parity_only: print('PARITY',nt,nd,flush=True);return
    config=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),label='post-outcome locally frozen finite-pool subset sensitivity',seed=2026102901,draws=5000,budgets=[20,40,80,'full'],alpha=.05,methods=METHODS,keys=KEYS,script_sha256=sha(Path(__file__)),input_sha256=sha(data),sampling='independent subsets per project and budget; within subset no replacement; same IDs for all keys/methods',inference='descriptive selection sensitivity conditional on this earlier pool and fixed later evaluation, not a future CI')
    freeze=OUT/'p1_freeze.json';assert not freeze.exists(),'refuse overwrite of frozen run'
    write('p1_freeze.json',config)
    rng=np.random.default_rng(config['seed']); results=[]; arrays={}; agg={}; missing_report=[]
    def summarize(scope,repo,key,budget,arr):
        for mi,m in enumerate(METHODS):
            out=dict(scope=scope,repo=repo,key=key,budget=budget,method=m,draws=len(arr))
            for vi,v in enumerate(METRICS):
                a=arr[:,mi,vi]; q=np.quantile(a,[.025,.5,.975]); out[v]=dict(mean=float(a.mean()),q025=float(q[0]),median=float(q[1]),q975=float(q[2]))
                if v=='infinite_threshold' and scope=='project_key':out[v]['mc_se']=float(np.sqrt(a.mean()*(1-a.mean())/len(a))) if len(a)>1 else 0.
            results.append(out)
    for ri,(repo,(ids,cube,missing,tests)) in enumerate(prepared.items()):
        missing_report.append(dict(repo=repo,calibration_size=len(ids),keys={str(k):dict(calibration_unknown=int(missing[:,ki].sum()),later_unknown=sum(not all(available(r,g) for g in ('negative_before','negative_after')) for r in tests[k]),later_n=len(tests[k])) for ki,k in enumerate(KEYS)}))
        for budget in config['budgets']:
            n=len(ids) if budget=='full' else budget; draws=1 if budget=='full' else config['draws']
            selected=np.arange(len(ids))[None,:] if budget=='full' else np.array([rng.choice(len(ids),size=n,replace=False) for _ in range(draws)])
            rank=math.ceil((n+1)*.95)
            thresh=np.partition(cube[selected],rank-1,axis=1)[:,rank-1,:,:] if rank<=n else np.full((draws,3,6),np.inf)
            stats=np.empty((draws,3,6,4))
            for ki,key in enumerate(KEYS):
                tt=tests[key]; complete=np.array([all(available(r,g) for g in ('negative_before','negative_after')) for r in tt])
                emb=np.array([r.get('embedding',{}).get('status')=='ok' for r in tt])
                for mi,m in enumerate(METHODS):
                    h=thresh[:,ki,mi,None]
                    positive=np.array([value(r,'positive_after',m) for r in tt])
                    negative=np.array([max(value(r,g,m) if available(r,g) else -math.inf for g in ('negative_before','negative_after')) for r in tt])
                    alarms=negative[None,:]>h
                    stats[:,ki,mi,0]=((positive[None,:]>h)&emb[None,:]).mean(axis=1)
                    stats[:,ki,mi,1]=alarms.mean(axis=1)
                    stats[:,ki,mi,2]=(alarms|~complete[None,:]).mean(axis=1)
                    stats[:,ki,mi,3]=np.isposinf(thresh[:,ki,mi])
                summarize('project_key',repo,key,budget,stats[:,ki])
            summarize('project_mean',repo,None,budget,stats.mean(axis=1))
            agg.setdefault(str(budget),[]).append(stats.mean(axis=1))
            prefix=f'p{ri}_b{budget}';arrays[prefix+'_indices']=selected.astype(np.int16);arrays[prefix+'_thresholds']=thresh;arrays[prefix+'_metrics']=stats
            print('BUDGET',repo,budget,flush=True)
    for budget,items in agg.items():summarize('equal_project_mean',None,None,int(budget) if budget!='full' else budget,np.mean(items,axis=0))
    np.savez_compressed(OUT/'p1_draws.npz',**arrays)
    assert sha(data)==config['input_sha256']
    write('p1_results.json',dict(config=config,pools=missing_report,summaries=results,quantiles='empirical 2.5/50/97.5 percentiles; NOT confidence intervals',mc_note='5000 draws; maximum Monte Carlo SE for a probability is sqrt(.25/5000)=0.007071; full pool deterministic',raw_sha256=sha(OUT/'p1_draws.npz')))
    print('P1_COMPLETE',len(results),flush=True)
if __name__=='__main__':main()
