"""Hold calibration size/unit fixed while changing source project; post hoc."""
import collections,json
from pathlib import Path
from analyze_upgrade import value,METHODS
from analyze_project_local import threshold
from negative_audit import supplement
ROOT=Path(__file__).resolve().parents[1]
def main():
    rows=supplement([json.loads(s) for s in (ROOT/'results/project_local_scores.jsonl').read_text().splitlines()],'v2')
    out=[];ts=[]
    primary=json.loads((ROOT/'results/project_local_summary.json').read_text())['summary']
    for lang in ('python','java'):
        repos=sorted({r['repo'] for r in rows if r['language']==lang})
        for source in repos:
            for target in repos:
                for method in METHODS:
                    counts=collections.Counter()
                    for key in (15485863,32452843,49979687):
                        cal=[r for r in rows if r['repo']==source and r['split']=='calibration' and r['key']==key]
                        test=[r for r in rows if r['repo']==target and r['split']=='test' and r['key']==key]
                        assert len(cal)==len(test)==80
                        t,n,k=threshold([max(value(r,g,method) for g in ('negative_before','negative_after')) for r in cal],.05)
                        ts.append(dict(source=source,target=target,method=method,key=key,threshold=t,n=n,rank=k))
                        for r in test:
                            counts['n']+=1
                            counts['negative_any']+=max(value(r,g,method) for g in ('negative_before','negative_after'))>t
                            counts['positive_after']+=r.get('embedding',{}).get('status')=='ok' and value(r,'positive_after',method)>t
                    d=dict(source=source,target=target,language=lang,method=method,**counts)
                    if source==target:
                        expected=next(x for x in primary if (x['repo'],x['method'],x['mode'],x['alpha'])==(target,method,'local_paired',.05))
                        assert all(d[k]==expected[k] for k in counts),(d,expected)
                    out.append(d)
    (ROOT/'results/calibration_source_control.json').write_text(json.dumps(dict(summary=out,thresholds=ts,interpretation='Post hoc; sample size80 and file-pair maximum aggregation held fixed. Self-project cells exactly reproduce primary results.'),indent=2))
    print(json.dumps([r for r in out if r['method']=='structured64']))
if __name__=='__main__':main()
