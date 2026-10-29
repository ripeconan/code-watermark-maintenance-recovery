"""Temporal-transfer audit with stage missingness and clustered descriptions."""
import collections,gzip,json,math
from pathlib import Path
import numpy as np
from analyze_upgrade import METHODS,value
ROOT=Path(__file__).resolve().parents[1]
PRIMARY=('official','syntax','structured64','nearest64','dictionary64','dictionary_pairs64')

def cutoff(values,alpha):
    values=sorted(values);rank=math.ceil((len(values)+1)*(1-alpha))
    return (values[rank-1] if 0<rank<=len(values) else float('inf')),rank

def available(row,group):
    return bool(row.get('group_scores',{}).get(group))

def encoded(x):
    return x if math.isfinite(x) else str(x)

def main():
    rows=[json.loads(s) for s in (ROOT/'results/temporal_scores.jsonl').read_text().splitlines() if s]
    raw=[r for p in (ROOT/'data/pairs').glob('*.json.gz') if '.frame.' not in p.name for r in json.loads(gzip.decompress(p.read_bytes()))]
    assert len(rows)==len(raw)*3,(len(rows),len(raw)*3)
    assert len({(r['id'],r['key']) for r in rows})==len(rows)
    external={(r['language'],r['key'],r['method'],r['alpha']):float(r['threshold']) for r in json.loads((ROOT/'records/external_thresholds.json').read_text())}
    thresholds=[];decisions=[];flow=[];coverage=[]
    for repo in sorted({r['repo'] for r in rows}):
        rr=[r for r in rows if r['repo']==repo];tt=[r for r in rr if r['split']=='test'];lang=rr[0]['language']
        flow.append(dict(repo=repo,language=lang,calibration_transitions=len({r['id'] for r in rr if r['split']=='calibration'}),test_transitions=len({r['id'] for r in tt}),test_commits=len({r['sha'] for r in tt}),test_paths=len({r['filename'] for r in tt}),attempts=len(tt),embedding=dict(collections.Counter(r.get('embedding',{}).get('status','missing') for r in tt)),replay=dict(collections.Counter(r.get('merge_status','not_completed') for r in tt)),process_errors=sum('error' in r for r in rr),stage_errors=sum(bool(r.get('stage_errors')) for r in rr),negative_incomplete=sum(not all(available(r,g) for g in ('negative_before','negative_after')) for r in tt)))
        changed=[r for r in tt if r.get('embedding',{}).get('status')=='ok' and r.get('merge_status')=='clean' and r.get('marked_context_changed') and r.get('group_scores',{}).get('positive_after',{}).get('official',{}).get('n_grades',0)>=5]
        for method in METHODS:
            coverage.append(dict(repo=repo,method=method,eligible_changed_attempts=len(changed),eligible_changed_transitions=len({r['id'] for r in changed}),old_context_included=sum(r['group_scores']['positive_after']['coverage'].get(method,False) for r in changed)))
        for key in sorted({r['key'] for r in rr}):
            cal=[r for r in rr if r['split']=='calibration' and r['key']==key];test=[r for r in tt if r['key']==key]
            for method in METHODS:
                for alpha in (.01,.05,.10):
                    for mode,groups in [('earlier_paired',('negative_before','negative_after')),('earlier_original',('negative_before',)),('external',None)]:
                        if groups:
                            missing=sum(not all(available(r,g) for g in groups) for r in cal)
                            vals=[max(value(r,g,method) if available(r,g) else float('inf') for g in groups) for r in cal]
                            threshold,rank=cutoff(vals,alpha);n=len(vals)
                        else:threshold=external[lang,key,method,alpha];rank=n=missing=None
                        thresholds.append(dict(repo=repo,key=key,method=method,alpha=alpha,mode=mode,n=n,rank=rank,missing_calibration_pairs=missing,threshold=encoded(threshold)))
                        for r in test:
                            complete=all(available(r,g) for g in ('negative_before','negative_after'))
                            neg=any(available(r,g) and value(r,g,method)>threshold for g in ('negative_before','negative_after'))
                            emb=r.get('embedding',{}).get('status')=='ok'
                            decisions.append(dict(repo=repo,id=r['id'],sha=r['sha'],filename=r['filename'],timestamp=r['timestamp'],key=key,method=method,alpha=alpha,mode=mode,negative_complete=complete,negative_any=neg,negative_upper=neg or not complete,positive_before=emb and value(r,'positive_before',method)>threshold,positive_after=emb and value(r,'positive_after',method)>threshold,embedding_ok=emb,clean=r.get('merge_status')=='clean'))
    grouped=collections.defaultdict(list)
    for r in decisions:grouped[r['repo'],r['mode'],r['method'],r['alpha']].append(r)
    summaries=[]
    metrics=('negative_any','negative_upper','negative_complete','positive_before','positive_after')
    for (repo,mode,method,alpha),rr in grouped.items():
        summaries.append(dict(repo=repo,mode=mode,method=method,alpha=alpha,n=len(rr),**{g:sum(r[g] for r in rr) for g in metrics}))
    intervals=[];rng=np.random.default_rng(2026102806)
    for repo in sorted({r['repo'] for r in rows}):
        rr=[r for r in decisions if r['repo']==repo and r['mode']=='earlier_paired' and r['alpha']==.05]
        if not rr:continue
        byid={r['id']:r for r in rr};ids=sorted(byid,key=lambda k:(byid[k]['timestamp'],byid[k]['sha']))
        clusters=collections.defaultdict(list)
        for i,uid in enumerate(ids):clusters[byid[uid]['filename']].append(i)
        n=len(ids);length=math.ceil(math.sqrt(n));blocks=math.ceil(n/length)
        cluster_arrays=[np.array(v,dtype=int) for _,v in sorted(clusters.items())]
        for metric in ('positive_after','negative_any'):
            values={}
            for method in PRIMARY:
                d=collections.defaultdict(list)
                for r in rr:
                    if r['method']==method:d[r['id']].append(float(r[metric]))
                values[method]=np.array([np.mean(d[uid]) for uid in ids])
            for comparator in ('official','syntax','nearest64','dictionary64','dictionary_pairs64'):
                delta=values['structured64']-values[comparator]
                cluster_sums=np.array([delta[a].sum() for a in cluster_arrays]);sizes=np.array([len(a) for a in cluster_arrays])
                draws=rng.integers(0,len(sizes),(5000,len(sizes)))
                cluster_means=cluster_sums[draws].sum(axis=1)/sizes[draws].sum(axis=1)
                starts=rng.integers(0,n,(5000,blocks))
                block_indices=((starts[:,:,None]+np.arange(length))%n).reshape(5000,-1)[:,:n]
                block_means=delta[block_indices].mean(axis=1)
                intervals.append(dict(repo=repo,metric=metric,comparison='structured64-minus-'+comparator,n_transitions=n,n_filename_clusters=len(sizes),temporal_block_length=length,mean=float(delta.mean()),filename_cluster_interval=list(map(float,np.quantile(cluster_means,[.025,.975]))),temporal_block_interval=list(map(float,np.quantile(block_means,[.025,.975])))))
    aggregate=[]
    for mode in ('earlier_paired','earlier_original','external'):
        for method in METHODS:
            for alpha in (.01,.05,.10):
                ss=[s for s in summaries if s['mode']==mode and s['method']==method and s['alpha']==alpha and s['n']]
                aggregate.append(dict(mode=mode,method=method,alpha=alpha,projects=len(ss),**{g:sum(s[g]/s['n'] for s in ss)/len(ss) if ss else None for g in metrics}))
    result=dict(records=len(rows),flow=flow,thresholds=thresholds,summary=summaries,coverage=coverage,paired_descriptive_intervals=intervals,equal_project_means=aggregate,interpretation='Temporal transfer of frozen detector policies; no exchangeability or future-risk guarantee. Unknown negatives are explicit. Intervals condition on fitted thresholds and are descriptive. Functional validation is separate.')
    (ROOT/'results/temporal_summary.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    with (ROOT/'results/temporal_decisions.jsonl').open('w') as f:
        for r in decisions:f.write(json.dumps(r)+'\n')
    report=['TEMPORAL EXTERNAL VALIDITY','Rows: '+str(len(rows)),'Primary alpha=0.05; detection and observed/upper-bound alarms over all attempts.']
    for repo in sorted({r['repo'] for r in rows}):
        report.append('\n'+repo)
        for s in summaries:
            if s['repo']==repo and s['mode']=='earlier_paired' and s['alpha']==.05 and s['method'] in PRIMARY:
                report.append(f"{s['method']:20s} detection {s['positive_after']}/{s['n']}; alarms {s['negative_any']}..{s['negative_upper']}/{s['n']}")
    (ROOT/'results/TEMPORAL_REPORT.txt').write_text('\n'.join(report)+'\n')
    print('\n'.join(report),flush=True)

if __name__=='__main__':main()
