"""Post-review diagnostics on unchanged scores; no deployable threshold fitting."""
import collections,json,math
from pathlib import Path
import numpy as np
from analyze_upgrade import value
from negative_audit import supplement
ROOT=Path(__file__).resolve().parents[1]
METHODS=('official','syntax','structured64','nearest64','dictionary64','dictionary_pairs64')

def roc_at(negative,positive,target=.05):
    # Sweep only finite scores: abstentions never become positive decisions.
    thresholds=sorted({x for x in negative+positive if math.isfinite(x)},reverse=True)
    points=[(0.,0.)]
    for t in thresholds:
        points.append((sum(x>=t for x in negative)/len(negative),sum(x>=t for x in positive)/len(positive)))
    # Preserve vertical segments by taking the greatest sensitivity at each FPR.
    best={}
    for x,y in points:best[x]=max(y,best.get(x,0))
    xs=sorted(best);ys=[best[x] for x in xs]
    return float(np.interp(target,xs,ys)),list(zip(xs,ys))

def main():
    rows=supplement([json.loads(s) for s in (ROOT/'results/project_local_scores.jsonl').read_text().splitlines()],'v2')
    rows=[r for r in rows if r['split']=='test'];out=[];curves=[]
    for repo in sorted({r['repo'] for r in rows}):
        for method in METHODS:
            rates=[]
            for key in (15485863,32452843,49979687):
                rr=[r for r in rows if r['repo']==repo and r['key']==key];assert len(rr)==80
                neg=[max(value(r,g,method) for g in ('negative_before','negative_after')) for r in rr]
                pos=[value(r,'positive_after',method) if r.get('embedding',{}).get('status')=='ok' else float('-inf') for r in rr]
                rate,curve=roc_at(neg,pos);rates.append(rate)
                curves.append(dict(repo=repo,method=method,key=key,points=curve))
            out.append(dict(repo=repo,method=method,mean_sensitivity=sum(rates)/3,per_key=rates,n_files=80))
    d=dict(summary=out,curves=curves,interpretation='Post hoc within-key ROC interpolation at empirical 5% either-version alarms; not deployment or functional evidence; unavailable positives never detected.')
    (ROOT/'results/project_diagnostic_roc.json').write_text(json.dumps(d,indent=2));print(json.dumps(out))
if __name__=='__main__':main()
