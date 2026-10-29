"""Recompute the historical extension with the complete official decision rule."""
import argparse,json,math,os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import numpy as np,pandas as pd


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    rows=[]
    for line in Path(a.input).read_text().split('\n'):
        if not line:continue
        r=json.loads(line)
        for group in ('positive','negative'):
            for edit in ('original','formatter','strip_comments','dead_return'):
                v=r[group].get(edit);s=v['score'] if v else {};p=s.get('p',1.);g=s.get('n_grades',0)
                verdict=s.get('verdict')=='Watermark detected'
                assert verdict==(bool(v) and g>=5 and p<.01)
                rows.append(dict(model=r['model'],mode=r['mode'],task_id=r['task_id'],key=r['key'],group=group,edit=edit,
                   available=bool(v),correct=bool(v and v['test']['ok']),grades=g,official=verdict,legacy=bool(v and p<.01),p=p,
                   source_correct=bool(r['negative'].get('original',{}).get('test',{}).get('ok')),
                   retained_grades=v.get('retained_grades',0) if v else 0,source_grades=v.get('source_grade_count',0) if v else 0))
    df=pd.DataFrame(rows);df['fold']=df.task_id.map(lambda x:int(x.split('/')[-1])%5)
    df['score']=np.where(df.available&(df.grades>=5),-df.p,-np.inf)
    for regime in ('matched','frozen'):
        df[regime]=False
        for _,d in df.groupby(['model','mode','key']):
            for edit,e in d.groupby('edit'):
                for fold in range(5):
                    n=d[(d.group=='negative')&(d.fold!=fold)&d.available&(d.edit==(edit if regime=='matched' else 'original'))].score.to_numpy()
                    rank=math.ceil((len(n)+1)*.95);threshold=np.sort(n)[rank-1] if 0<rank<=len(n) else np.inf
                    ix=e.index[e.fold==fold];df.loc[ix,regime]=df.loc[ix,'score']>threshold
    out=[];contrasts=[]
    from analyze_recovery import interval
    for keys,d in df.groupby(['model','mode','group','edit']):
        for method in ('official','legacy','matched','frozen'):
            out.append(dict(zip(('model','mode','group','edit'),keys),method=method,n=len(d),detected=int(d[method].sum()),
                 joint_count=int((d[method]&d.correct).sum()),detection=interval(d,d[method]),joint=interval(d,d[method]&d.correct),
                 eligible=int((d.available&(d.grades>=5)).sum()),correct=int(d.correct.sum())))
    for keys,d in df[df.group=='positive'].groupby(['model','edit']):
        for method in ('official','matched','frozen'):
            d=d.copy();d['joint']=(d[method]&d.correct).astype(int)
            wide=d.pivot(index=['task_id','key'],columns='mode',values='joint').reset_index()
            contrasts.append(dict(model=keys[0],edit=keys[1],method=method,delta_joint=interval(wide,wide.no_global-wide.official)))
    dest=Path(a.out);dest.mkdir(parents=True,exist_ok=True)
    df.to_csv(dest/'sew_corrected_rows.csv',index=False)
    (dest/'sew_corrected_summary.json').write_text(json.dumps({'summary':out,'contrasts':contrasts},indent=2))
    for r in out:
        if r['group']=='positive' and r['edit'] in ('original','dead_return') and r['method'] in ('official','matched'):
            print(r['model'],r['mode'],r['edit'],r['method'],r['detected'],r['joint_count'],'/',r['n'])


if __name__=='__main__':main()
