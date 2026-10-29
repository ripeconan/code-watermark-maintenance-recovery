"""External-distribution transfer on actual public patch replays; no functional claim."""
import json
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
records=[json.loads(s) for s in (ROOT/'results/real_patch_replay.jsonl').read_text().split('\n') if s]
thresholds=json.loads((ROOT/'results/confirmation_summary.json').read_text())['thresholds']
lookup={(r['language'],r['key'],r['method']):float(r['threshold']) for r in thresholds if r['regime']=='envelope' and r['alpha']==.05}
methods=('official','syntax','nearest_budget','l1_3');rows=[]
for r in records:
    for group in ('negative_before','negative_after','positive_before','positive_after'):
        d=r['group_scores'].get(group,{});eligible=d.get('official',{}).get('n_grades',0)>=5
        for method in methods:
            score=-d.get('scores',{}).get(method,1.) if eligible else -np.inf
            rows.append(dict(repo=r['repo'],sha=r['sha'],filename=r['filename'],language=r['language'],key=r['key'],
                 family=r['family'],group=group,method=method,available=bool(d),merge_status=r['merge_status'],
                 detected=score>lookup[r['language'],r['key'],method],eligible=eligible,
                 embedding_ok=r.get('embedding',{}).get('status')=='ok'))
df=pd.DataFrame(rows);out=[]
def interval(d):
    g=d.groupby('repo').detected.agg(['sum','count']).to_numpy();rng=np.random.default_rng(20261030)
    b=g[rng.integers(len(g),size=(4000,len(g)))].sum(axis=1);v=b[:,0]/b[:,1]
    return dict(mean=float(d.detected.mean()),lo=float(np.quantile(v,.025)),hi=float(np.quantile(v,.975)),projects=len(g))
for keys,d in df.groupby(['language','group','method']):
    out.append(dict(zip(('language','group','method'),keys),n=len(d),available=int(d.available.sum()),
                    detected=int(d.detected.sum()),rate=interval(d),clean_merge=int((d.merge_status=='clean').sum())))
flow={}
for lang in ('python','java'):
    rr=[r for r in records if r['language']==lang]
    flow[lang]=dict(pairs=len(rr),files=len({(r['repo'],r['sha'],r['filename']) for r in rr}),projects=len({r['repo'] for r in rr}),
       clean=sum(r['merge_status']=='clean' for r in rr),conflicts=sum(r['merge_status']=='conflict' for r in rr),
       errors=sum(bool(r.get('error') or r.get('group_errors')) for r in rr))
(ROOT/'results/real_patch_summary.json').write_text(json.dumps(dict(flow=flow,summary=out),indent=2))
df.to_csv(ROOT/'results/real_patch_rows.csv',index=False)
print('PATCH_FLOW',flow,flush=True)
for r in out:
    if r['group'].endswith('after'):print(r['language'],r['group'],r['method'],r['detected'],r['n'],'available',r['available'],flush=True)
