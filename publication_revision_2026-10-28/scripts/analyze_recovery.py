"""Negative-only calibration and task-cluster summaries; no code execution."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse,json,math
from pathlib import Path
import numpy as np
import pandas as pd


def interval(d, values):
    x=pd.Series(np.asarray(values,dtype=float),index=d.index).groupby(d.task_id).mean().to_numpy()
    rng=np.random.default_rng(20261028)
    b=x[rng.integers(len(x),size=(3000,len(x)))].mean(axis=1)
    return {'mean':float(x.mean()),'lo':float(np.quantile(b,.025)),'hi':float(np.quantile(b,.975)),'tasks':len(x)}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    df=pd.read_json(a.input,lines=True)
    df['fold']=df.task_id.map(lambda x:int(x.split('/')[-1])%5)
    df['eligible']=df.available & (df.n_grades>=5)
    for score in ('p','scan1','scan2','oracle'):
        df['score_'+score]=np.where(df.eligible,-df[score],-np.inf)
        for regime in ('matched','frozen','envelope'):
            col=regime+'_'+score;df[col]=False
            for (model,key),d in df.groupby(['model','key']):
                for edit,e in d.groupby('edit'):
                    for fold in range(5):
                        train=d[(d.group=='negative')&(d.fold!=fold)&d.available]
                        if regime=='envelope':
                            n=train.groupby('task_id')['score_'+score].max().to_numpy()
                        else:
                            n=train[train.edit==(edit if regime=='matched' else 'original')]['score_'+score].to_numpy()
                        rank=math.ceil((len(n)+1)*.95)
                        threshold=np.sort(n)[rank-1] if 0<rank<=len(n) else np.inf
                        ix=e.index[e.fold==fold]
                        df.loc[ix,col]=df.loc[ix,'eligible'] & (df.loc[ix,'score_'+score]>threshold)
    for score in ('scan1','scan2','bonf1','bonf2','oracle'):
        df['nominal_'+score]=df.eligible & (df[score]<.01)
    methods=['official','legacy']+[x+'_'+s for x in ('matched','frozen','envelope') for s in ('p','scan1','scan2','oracle')]+['nominal_'+s for s in ('scan1','scan2','bonf1','bonf2','oracle')]
    summary=[]
    for (model,group,edit),d in df.groupby(['model','group','edit']):
        for method in methods:
            summary.append(dict(model=model,group=group,edit=edit,method=method,n=len(d),
                detected=int(d[method].sum()),joint_count=int((d[method]&d.correct).sum()),
                detection=interval(d,d[method]),joint=interval(d,d[method]&d.correct),
                eligible=int(d.eligible.sum()),available=int(d.available.sum())))
    contrasts=[]
    for (model,edit),d in df[df.group=='positive'].groupby(['model','edit']):
        for method in ('matched_scan1','matched_scan2','frozen_scan1','frozen_scan2','envelope_scan1','envelope_scan2'):
            baseline=method.split('_')[0]+'_p'
            delta=(d[method]&d.correct).astype(int)-(d[baseline]&d.correct).astype(int)
            contrasts.append(dict(model=model,edit=edit,method=method,baseline=baseline,delta_joint=interval(d,delta)))
    dest=Path(a.out);dest.mkdir(parents=True,exist_ok=True)
    df.to_csv(dest/'recovery_rows.csv',index=False)
    (dest/'recovery_summary.json').write_text(json.dumps({'summary':summary,'contrasts':contrasts,'seed':20261028,'bootstrap':3000},indent=2))
    print('OFFICIAL AND RECOVERY, matched/frozen calibration at target 5%',flush=True)
    for r in summary:
        if r['edit'] in ('original','dead_return','formatter') and r['method'] in ('official','matched_p','matched_scan1','frozen_p','frozen_scan1','envelope_p','envelope_scan1'):
            print(r['model'],r['group'],r['edit'],r['method'],r['detected'],r['joint_count'],'/',r['n'])


if __name__=='__main__':main()
