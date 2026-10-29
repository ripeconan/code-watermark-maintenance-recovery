"""Post-review diagnostics; ROC thresholds are descriptive, never deployment fits."""
import json,math
from pathlib import Path
import numpy as np,pandas as pd
from analyze_confirmation import ci
ROOT=Path(__file__).resolve().parents[1]
d=pd.read_csv(ROOT/'results/confirmation_scores.csv');d=d[d.split=='test']
dec=pd.read_csv(ROOT/'results/confirmation_test_decisions.csv.gz');dec=dec[(dec.regime=='envelope')&(dec.alpha==.05)]
methods=('official','delta_dictionary','syntax','l1_3','l1_4')

def roc_value(p,n,limit=.05):
    # Keep the evidence gate: nonfinite scores are never detected.
    vals=np.r_[p,n];finite=np.isfinite(vals);v=vals[finite]
    labels=np.r_[np.ones(len(p)),np.zeros(len(n))][finite]
    order=np.argsort(-v,kind='stable');v=v[order];labels=labels[order]
    if not len(v):return 0.,0.
    ix=np.r_[np.nonzero(v[:-1]!=v[1:])[0],len(v)-1]
    tp=np.r_[0.,np.cumsum(labels)[ix]/len(p)];fp=np.r_[0.,np.cumsum(1-labels)[ix]/len(n)]
    # The last point at each FPR retains the upper end of vertical ROC segments.
    unique=np.unique(fp);power=np.array([tp[fp==x].max() for x in unique])
    if unique[-1]<limit:unique=np.r_[unique,limit];power=np.r_[power,power[-1]]
    at=float(np.interp(limit,unique,power));x=np.r_[unique[unique<limit],limit];y=np.interp(x,unique,power)
    integrate=getattr(np,'trapezoid',None) or np.trapz
    return at,float(integrate(y,x)/limit)

roc=[]
for (lang,edit,method),g in d[d.method.isin(methods)].groupby(['language','edit','method']):
    ids=sorted(g.id.unique());keys=sorted(g.key.unique());arrays=[]
    for key in keys:
        sub=g[g.key==key];p=sub[sub.group=='positive'].set_index('id').reindex(ids);n=sub[sub.group=='negative'].set_index('id').reindex(ids)
        arrays.append((p.score.to_numpy(),n.score.to_numpy(),p.correct.to_numpy()))
    values=[]
    for endpoint in ('detection','joint'):
        samples=[]
        for p,n,ok in arrays:
            samples.append(roc_value(p if endpoint=='detection' else np.where(ok,p,-np.inf),n))
        est=np.mean(samples,axis=0);rng=np.random.default_rng(20261031);bs=[]
        for _ in range(400):
            ix=rng.integers(len(ids),size=len(ids));rep=[]
            for p,n,ok in arrays:rep.append(roc_value((p if endpoint=='detection' else np.where(ok,p,-np.inf))[ix],n[ix]))
            bs.append(np.mean(rep,axis=0))
        bs=np.array(bs)
        roc.append(dict(language=lang,edit=edit,method=method,endpoint=endpoint,problems=len(ids),target_fpr=.05,
            tpr=float(est[0]),tpr_lo=float(np.quantile(bs[:,0],.025)),tpr_hi=float(np.quantile(bs[:,0],.975)),
            normalized_partial_auc=float(est[1]),pauc_lo=float(np.quantile(bs[:,1],.025)),pauc_hi=float(np.quantile(bs[:,1],.975))))
noedit=[]
for lang in ('python','java','cpp'):
    sub=dec[(dec.language==lang)&(dec.group=='positive')&(dec.method.isin(['official','syntax']))].copy();sub['joint']=sub.detected&sub.correct
    wide=sub.pivot(index=['id','key'],columns=['method','edit'],values='joint').astype(int)
    premium=wide['syntax','original']-wide['official','original']
    for edit in ('helper','helper_loop','formatter_helper'):
        gain=wide['syntax',edit]-wide['official',edit];diff=gain-premium
        noedit.append(dict(language=lang,edit=edit,no_edit_search_difference=ci(premium.groupby(level=0).mean()),maintenance_difference=ci(diff.groupby(level=0).mean())))
perkey=[]
for keys,g in dec[dec.method.isin(methods)].groupby(['language','key','method','group','edit']):
    perkey.append(dict(zip(['language','key','method','group','edit'],keys),n=len(g),detected=int(g.detected.sum()),joint=int((g.detected&g.correct).sum())))
gates=[];conditional=[]
for lang in ('python','java','cpp'):
    sub=d[(d.language==lang)&(d.group=='positive')&(d.method=='official')]
    w=sub.pivot(index=['id','key'],columns='edit',values='eligible')
    for edit in ('helper','helper_loop','formatter','formatter_helper'):
        gates.append(dict(language=lang,edit=edit,n=len(w),became_eligible=int((~w.original&w[edit]).sum()),lost_eligibility=int((w.original&~w[edit]).sum())))
    for (method,edit),g in dec[(dec.language==lang)&(dec.group=='positive')&dec.method.isin(methods)].groupby(['method','edit']):
        good=g[g.source_correct];conditional.append(dict(language=lang,method=method,edit=edit,source_pass_records=len(good),
            detected=int(good.detected.sum()),joint=int((good.detected&good.correct).sum()),source_fail_records=int((~g.source_correct).sum())))
out=dict(roc=roc,no_edit_control=noedit,per_key=perkey,grade_gate_transitions=gates,conditional_source_pass=conditional,
    note='ROC uses test negatives descriptively with randomized interpolation of ties; it is not an independently calibrated operating point. Bootstrap: 400 problem resamples with all keys paired.')
(ROOT/'results/review_diagnostics.json').write_text(json.dumps(out,indent=2));print('REVIEW_DIAGNOSTICS',len(roc),flush=True);print(json.dumps(gates,indent=2))
