"""Validation-only thresholds, untouched test problems, paired problem inference."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse,json,math
from pathlib import Path
import numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1]
EDITS=('original','formatter','helper','formatter_helper','helper_loop')
ENVELOPE=EDITS[:-1]
METHODS=('official','l1_1','l1_2','l1_3','l1_4','syntax','nearest_budget','delta_dictionary','oracle')


def ci(x):
    x=np.asarray(x,dtype=float);rng=np.random.default_rng(20261028)
    if not len(x):return None
    samples=x[rng.integers(len(x),size=(4000,len(x)))].mean(axis=1)
    return dict(mean=float(x.mean()),lo=float(np.quantile(samples,.025)),hi=float(np.quantile(samples,.975)),problems=len(x))


def paired_p(x):
    x=np.asarray(x,dtype=float);observed=abs(x.mean());rng=np.random.default_rng(20261029)
    null=(x*rng.choice([-1,1],size=(19999,len(x)))).mean(axis=1)
    return float((1+np.sum(np.abs(null)>=observed-1e-15))/20000)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',default=str(ROOT/'results/confirmation_extended.jsonl'))
    ap.add_argument('--functional',default=str(ROOT/'results/confirmation_functional.jsonl'));ap.add_argument('--allow-incomplete-functional',action='store_true');a=ap.parse_args()
    records=[json.loads(s) for s in Path(a.input).read_text().split('\n') if s]
    assert len(records)==2079,len(records)
    assert len({(r['id'],r['language'],r['key']) for r in records})==2079
    checks={}
    if Path(a.functional).exists():
        text=Path(a.functional).read_text();complete=text.split('\n')
        if not text.endswith('\n'):complete=complete[:-1]
        for line in complete:
            if line:
                r=json.loads(line)
                for c in r['results']:checks[r['id'],r['language'],c['sha256']]=c
    missing=set();rows=[]
    for r in records:
        for group in ('negative','positive'):
            for edit in EDITS:
                v=r['groups'][group]['variants'].get(edit);d=v['detection'] if v else {};o=d.get('official',{})
                qc=checks.get((r['id'],r['language'],v['sha256'])) if v else None
                if v and qc is None:missing.add((r['id'],r['language'],v['sha256']))
                for method in METHODS:
                    p=d.get('scores',{}).get(method,1.);grades=o.get('n_grades',0)
                    rows.append(dict(id=r['id'],split=r['split'],language=r['language'],key=r['key'],group=group,edit=edit,
                        method=method,available=bool(v),grades=grades,eligible=bool(v and grades>=5),
                        score=-p if v and grades>=5 else -np.inf,p=p,
                        nominal=bool(v and grades>=5 and (o['verdict']=='Watermark detected' if method=='official' else p*max(1,d.get('candidates',{}).get(method,1))<.01)),
                        candidates=d.get('candidates',{}).get(method,0),seconds=d.get('seconds',0),
                        functional_known=qc is not None,correct=bool(qc and qc.get('benchmark_pass')),
                        preserved=bool(qc and qc.get('behavior_preserved')),
                        source_correct=bool(qc and qc.get('source_benchmark_pass')),
                        embedding_ok=r['embedding'].get('status')=='ok'))
    if missing and not a.allow_incomplete_functional:raise ValueError(('Missing functional records',len(missing)))
    df=pd.DataFrame(rows);thresholds=[];summaries=[];contrasts=[];test_rows=[]
    for (lang,key,method),d in df.groupby(['language','key','method']):
        train=d[(d.split=='valid')&(d.group=='negative')]
        for regime in ('frozen','pooled','envelope'):
            if regime=='frozen':cal=train[train.edit=='original'].score.to_numpy()
            elif regime=='pooled':
                # One prechosen transform per source, rather than treating correlated variants as IID.
                import hashlib
                chosen=train[train.edit.isin(ENVELOPE)].copy()
                mapping={pid:ENVELOPE[int.from_bytes(hashlib.sha256(pid.encode()).digest()[:4],'big')%len(ENVELOPE)] for pid in chosen.id.unique()}
                cal=chosen[chosen.edit==chosen.id.map(mapping)].score.to_numpy()
            else:cal=train[train.edit.isin(ENVELOPE)].groupby('id').score.max().to_numpy()
            for alpha in (.01,.05,.10):
                rank=math.ceil((len(cal)+1)*(1-alpha));tau=float(np.sort(cal)[rank-1]) if 0<rank<=len(cal) else float('inf')
                thresholds.append(dict(language=lang,key=int(key),method=method,regime=regime,alpha=alpha,n=len(cal),threshold=tau if np.isfinite(tau) else str(tau)))
                t=d[d.split=='test'].copy();t['detected']=t.score>tau;t['regime']=regime;t['alpha']=alpha
                test_rows.append(t)
    test=pd.concat(test_rows,ignore_index=True)
    for keys,d in test.groupby(['language','method','regime','alpha','group','edit']):
        per=d.groupby('id')[['detected','correct','preserved']].mean()
        joint=(d.detected&d.correct).groupby(d.id).mean()
        summaries.append(dict(zip(('language','method','regime','alpha','group','edit'),keys),n=len(d),
            detected=int(d.detected.sum()),joint_count=int((d.detected&d.correct).sum()),correct=int(d.correct.sum()),
            preserved=int(d.preserved.sum()),available=int(d.available.sum()),eligible=int(d.eligible.sum()),
            detection=ci(per.detected),joint=ci(joint),functional_known=int(d.functional_known.sum()),
            candidates_mean=float(d.candidates.mean()),grades_median=float(d.grades.median())))
    for (lang,edit),d in test[(test.group=='positive')&(test.regime=='envelope')&(test.alpha==.05)].groupby(['language','edit']):
        d=d.copy();d['joint']=(d.detected&d.correct).astype(int)
        wide=d.pivot(index=['id','key'],columns='method',values='joint').reset_index()
        for target in ('syntax','l1_1','l1_2','l1_3','l1_4'):
            for baseline in ('official','nearest_budget','delta_dictionary'):
                delta=(wide[target]-wide[baseline]).groupby(wide.id).mean()
                contrasts.append(dict(language=lang,edit=edit,target=target,baseline=baseline,delta_joint=ci(delta),p=paired_p(delta)))
    primary=[x for x in contrasts if x['edit']=='helper' and x['target']=='syntax' and x['baseline']=='official']
    ordered=sorted(primary,key=lambda r:r['p']);running=0.
    for i,r in enumerate(ordered):running=max(running,min(1.,(len(ordered)-i)*r['p']));r['holm_p']=running
    # Global any-edit negative alarm at the envelope threshold, with one record per source/key.
    risk=[]
    for keys,d in test[(test.group=='negative')&(test.regime=='envelope')].groupby(['language','method','alpha']):
        grouped=d[d.edit.isin(ENVELOPE)].groupby(['id','key']).detected.max().reset_index()
        risk.append(dict(zip(('language','method','alpha'),keys),n=len(grouped),alarms=int(grouped.detected.sum()),interval=ci(grouped.groupby('id').detected.mean())))
    output=ROOT/'results';df.to_csv(output/'confirmation_scores.csv',index=False)
    test.to_csv(output/'confirmation_test_decisions.csv.gz',index=False,compression='gzip')
    (output/'confirmation_summary.json').write_text(json.dumps(dict(summary=summaries,contrasts=contrasts,thresholds=thresholds,
        envelope_risk=risk,missing_functional=len(missing),raw_records=len(records)),indent=2,allow_nan=False))
    print('CONFIRMATION_SUMMARY',len(records),'missing functional',len(missing),flush=True)
    for r in summaries:
        if r['regime']=='envelope' and r['alpha']==.05 and r['method'] in ('official','syntax','nearest_budget','l1_3') and r['edit'] in ('original','helper','formatter_helper','helper_loop'):
            print(r['language'],r['group'],r['edit'],r['method'],r['detected'],r['joint_count'],'/',r['n'],flush=True)


if __name__=='__main__':main()
