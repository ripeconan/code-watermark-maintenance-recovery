"""Frozen external/local/original-only calibration comparisons on the same tests."""
import collections,gzip,json,math
from pathlib import Path
import numpy as np
from analyze_upgrade import METHODS,value
ROOT=Path(__file__).resolve().parents[1]

def threshold(values,alpha):
    values=sorted(values);n=len(values);rank=math.ceil((n+1)*(1-alpha))
    t=values[rank-1] if 0<rank<=n else float('inf')
    return t,n,rank

def main():
    rows=[json.loads(s) for s in (ROOT/'results/project_local_scores.jsonl').read_text().splitlines() if s]
    from negative_audit import supplement
    rows=supplement(rows,'v2')
    expected=sum(len(json.loads(gzip.decompress(p.read_bytes())))*3 for p in (ROOT/'data/project_calibration').glob('*.json.gz') if '.frame.' not in p.name)
    assert len(rows)==expected,(len(rows),expected)
    assert len({(r['id'],r['key']) for r in rows})==len(rows)
    old=json.loads((ROOT/'results/upgrade_summary.json').read_text())
    external={(t['language'],t['key'],t['method'],t['alpha']):float(t['threshold']) for t in old['thresholds']}
    thresholds=[];decisions=[];flow=[];coverage=[]
    for repo in sorted({r['repo'] for r in rows}):
        rr=[r for r in rows if r['repo']==repo];test=[r for r in rr if r['split']=='test'];lang=rr[0]['language']
        flow.append(dict(repo=repo,language=lang,calibration_files=len({r['id'] for r in rr if r['split']=='calibration'}),test_files=len({r['id'] for r in test}),attempts=len(test),
            embedding=dict(collections.Counter(r.get('embedding',{}).get('status','error') for r in test)),
            replay=dict(collections.Counter(r.get('merge_status','error') for r in test)),errors=sum('error' in r for r in rr)))
        changed=[r for r in test if r.get('embedding',{}).get('status')=='ok' and r.get('merge_status')=='clean' and r.get('marked_context_changed') and r.get('group_scores',{}).get('positive_after',{}).get('official',{}).get('n_grades',0)>=5]
        for method in METHODS:
            coverage.append(dict(repo=repo,method=method,eligible_changed=len(changed),old_context_included=sum(r['group_scores']['positive_after']['coverage'].get(method,False) for r in changed)))
        for key in sorted({r['key'] for r in rr}):
            cal=[r for r in rr if r['split']=='calibration' and r['key']==key];tt=[r for r in test if r['key']==key]
            for method in METHODS:
                paired=[max(value(r,g,method) for g in ('negative_before','negative_after')) for r in cal]
                original=[value(r,'negative_before',method) for r in cal]
                for alpha in (.01,.05,.10):
                    for mode,vals in [('local_paired',paired),('local_original',original),('external',None)]:
                        t,n,rank=threshold(vals,alpha) if vals is not None else (external[lang,key,method,alpha],None,None)
                        thresholds.append(dict(repo=repo,key=key,method=method,alpha=alpha,mode=mode,n=n,rank=rank,threshold=t if math.isfinite(t) else str(t)))
                        for r in tt:
                            neg=[value(r,g,method)>t for g in ('negative_before','negative_after')]
                            emb=r.get('embedding',{}).get('status')=='ok'
                            decisions.append(dict(repo=repo,id=r['id'],sha=r['sha'],key=key,method=method,alpha=alpha,mode=mode,
                                negative_before=neg[0],negative_after=neg[1],negative_any=any(neg),
                                positive_before=emb and value(r,'positive_before',method)>t,
                                positive_after=emb and value(r,'positive_after',method)>t,
                                embedding_ok=emb,clean=r.get('merge_status')=='clean'))
    summary=[];groups=collections.defaultdict(list)
    for r in decisions:groups[r['repo'],r['mode'],r['method'],r['alpha']].append(r)
    for (repo,mode,method,alpha),rr in groups.items():
        summary.append(dict(repo=repo,mode=mode,method=method,alpha=alpha,n=len(rr),**{g:sum(r[g] for r in rr) for g in ('negative_before','negative_after','negative_any','positive_before','positive_after')}))
    # Paired key means, source-file resampling, thresholds held fixed. Descriptive
    # intervals do not include calibration-set uncertainty or certify deployment risk.
    intervals=[];rng=np.random.default_rng(2026102805)
    for repo in sorted({r['repo'] for r in rows}):
        rr=[r for r in decisions if r['repo']==repo and r['mode']=='local_paired' and r['alpha']==.05]
        for metric in ('positive_after','negative_any'):
            bymethod={}
            for method in ('official','syntax','structured64','nearest64','dictionary64','dictionary_pairs64'):
                d=collections.defaultdict(list)
                for r in rr:
                    if r['method']==method:d[r['id']].append(float(r[metric]))
                bymethod[method]={k:sum(v)/len(v) for k,v in d.items()}
            ids=sorted(bymethod['structured64'])
            for comparator in ('official','syntax','nearest64','dictionary64','dictionary_pairs64'):
                delta=np.array([bymethod['structured64'][i]-bymethod[comparator][i] for i in ids])
                draws=rng.integers(0,len(ids),(5000,len(ids)));means=delta[draws].mean(axis=1)
                intervals.append(dict(repo=repo,metric=metric,comparison='structured64-minus-'+comparator,n_files=len(ids),mean=float(delta.mean()),ci95=list(map(float,np.quantile(means,[.025,.975])))))
    out=dict(records=len(rows),flow=flow,thresholds=thresholds,summary=summary,coverage=coverage,paired_intervals=intervals,
        interpretation='Detection conditional on successful embedding, all attempts in denominator. No functional success implied. Intervals descriptive, conditional on calibration thresholds.')
    (ROOT/'results/project_local_summary.json').write_text(json.dumps(out,indent=2,allow_nan=False))
    with (ROOT/'results/project_local_decisions.jsonl').open('w') as f:
        for r in decisions:f.write(json.dumps(r)+'\n')
    print('FLOW',json.dumps(flow),flush=True)
    for repo in sorted({r['repo'] for r in rows}):
        print('PROJECT',repo)
        for mode in ('external','local_original','local_paired'):
            for method in ('official','syntax','structured64','nearest64','dictionary64','dictionary_pairs64'):
                d=next(r for r in summary if r['repo']==repo and r['mode']==mode and r['method']==method and r['alpha']==.05)
                print(mode,method,'positive_after',d['positive_after'],'negative_any',d['negative_any'],'n',d['n'])

if __name__=='__main__':main()
