"""Separate negative calibration, all-attempt outcomes and conditional coverage."""
import argparse,collections,json,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
METHODS=('official','syntax','structured64','structured128','nearest64','nearest128','l1_4','dictionary64','dictionary_pairs64')

def value(r,group,method):
    d=r.get('group_scores',{}).get(group,{})
    if d.get('official',{}).get('n_grades',0)<5 or method not in d.get('scores',{}):return float('-inf')
    return -d['scores'][method]

def main():
    rows=[json.loads(s) for s in (ROOT/'results/upgrade_scores.jsonl').read_text().splitlines() if s]
    from negative_audit import supplement
    rows=supplement(rows,'v1')
    assert len(rows)==1548,(len(rows),'unexpected complete denominator')
    assert len({(r['id'],r['key']) for r in rows})==len(rows)
    thresholds=[];summary=[];coverage=[];flow=[];decisions=[]
    languages=sorted({r['language'] for r in rows});keys=sorted({r['key'] for r in rows})
    for lang in languages:
        for key in keys:
            cal=[r for r in rows if r['split']=='calibration' and r['language']==lang and r['key']==key]
            test=[r for r in rows if r['split']=='test' and r['language']==lang and r['key']==key]
            for method in METHODS:
                bycommit=collections.defaultdict(list)
                for r in cal:bycommit[r['sha']].extend(value(r,g,method) for g in ('negative_before','negative_after'))
                vals=sorted(max(v) for v in bycommit.values());n=len(vals)
                for alpha in (.01,.05,.10):
                    rank=math.ceil((n+1)*(1-alpha));threshold=vals[rank-1] if 0<rank<=n else float('inf')
                    thresholds.append(dict(language=lang,key=key,method=method,alpha=alpha,n_commits=n,rank=rank,
                        threshold=threshold if math.isfinite(threshold) else str(threshold)))
                    for r in test:
                        for group in ('negative_before','negative_after','positive_before','positive_after'):
                            d=r.get('group_scores',{}).get(group,{})
                            embedding_ok=r.get('embedding',{}).get('status')=='ok'
                            detected=value(r,group,method)>threshold
                            # Do not count a positive detection as useful embedding recovery
                            # when the embedder itself abstained or failed.
                            usable=detected and (group.startswith('negative') or embedding_ok)
                            decisions.append(dict(id=r['id'],repo=r['repo'],sha=r['sha'],language=lang,key=key,method=method,alpha=alpha,
                                group=group,detected=detected,embedding_ok=embedding_ok,usable_detected=usable,
                                available=bool(d),eligible=d.get('official',{}).get('n_grades',0)>=5,
                                clean=r.get('merge_status')=='clean',marked_context_changed=r.get('marked_context_changed',False),
                                candidates=d.get('candidates',{}).get(method,0)))
    for lang in languages:
        rr=[r for r in rows if r['language']==lang and r['split']=='test']
        flow.append(dict(language=lang,attempts=len(rr),sources=len({r['id'] for r in rr}),commits=len({r['sha'] for r in rr}),
            embedding=dict(collections.Counter(r.get('embedding',{}).get('status','error') for r in rr)),
            replay=dict(collections.Counter(r.get('merge_status','error') for r in rr)),
            errors=sum('error' in r for r in rr)))
        for method in METHODS:
            after=[r for r in rr if r.get('embedding',{}).get('status')=='ok' and r.get('merge_status')=='clean' and r.get('marked_context_changed') and r.get('group_scores',{}).get('positive_after',{}).get('official',{}).get('n_grades',0)>=5]
            coverage.append(dict(language=lang,method=method,eligible_changed=len(after),
                old_context_included=sum(r['group_scores']['positive_after']['coverage'].get(method,False) for r in after)))
    grouped=collections.defaultdict(list)
    for r in decisions:grouped[(r['language'],r['method'],r['alpha'],r['group'])].append(r)
    for (lang,m,a,g),rs in grouped.items():
        summary.append(dict(language=lang,method=m,alpha=a,group=g,n=len(rs),detected=sum(r['detected'] for r in rs),
            usable_detected=sum(r['usable_detected'] for r in rs),eligible=sum(r['eligible'] for r in rs),
            available=sum(r['available'] for r in rs),candidates_mean=sum(r['candidates'] for r in rs)/len(rs)))
    # Paired source/commit records retained for later block-bootstrap intervals.
    output=dict(records=len(rows),thresholds=thresholds,flow=flow,coverage=coverage,summary=summary,
        interpretation='Detected-only results; project tests pending. Calibration uses commit maxima, with no certified cross-project risk claim.')
    (ROOT/'results/upgrade_summary.json').write_text(json.dumps(output,indent=2,allow_nan=False))
    with (ROOT/'results/upgrade_decisions.jsonl').open('w') as f:
        for r in decisions:f.write(json.dumps(r)+'\n')
    print('FLOW',json.dumps(flow),flush=True)
    for lang in languages:
        print('LANGUAGE',lang,'5% target: after positive useful/240; negative alarms/240; before useful/240')
        for m in METHODS:
            d={r['group']:r for r in summary if r['language']==lang and r['method']==m and r['alpha']==.05}
            c=next(r for r in coverage if r['language']==lang and r['method']==m)
            print(m,d['positive_after']['usable_detected'],d['negative_after']['detected'],d['positive_before']['usable_detected'],
                'old-context',c['old_context_included'],'/',c['eligible_changed'])

if __name__=='__main__':main()
