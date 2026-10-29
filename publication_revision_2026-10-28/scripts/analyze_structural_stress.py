import json
from pathlib import Path
import pandas as pd
from analyze_confirmation import ci
ROOT=Path(__file__).resolve().parents[1]
summary=json.loads((ROOT/'results/confirmation_summary.json').read_text())
tau={(r['language'],r['key'],r['method']):float(r['threshold']) for r in summary['thresholds'] if r['regime']=='envelope' and r['alpha']==.05}
checks={}
for r in map(json.loads,(ROOT/'results/structural_stress_functional.jsonl').read_text().splitlines()):
    for c in r['results']:checks[r['language'],r['id'],c['sha256']]=c
records=list(map(json.loads,(ROOT/'results/structural_stress_extended.jsonl').read_text().splitlines()));assert len(records)==216
rows=[];coverage=[];errors=[]
original={(r['language'],r['id'],r['key']):r for r in map(json.loads,(ROOT/'results/confirmation_augmented.jsonl').read_text().splitlines())}
for r in records:
    old=original[r['language'],r['id'],r['key']]
    for group in ('negative','positive'):
        if r['groups'][group]['errors']:errors.append(dict(id=r['id'],language=r['language'],key=r['key'],group=group,errors=r['groups'][group]['errors']))
        for edit in ('nested_helper','two_helpers'):
            v=r['groups'][group]['variants'].get(edit);d=v['detection'] if v else {};q=checks[r['language'],r['id'],v['sha256']] if v else {}
            ctx=old['groups'][group]['variants'].get('original',{}).get('detection',{}).get('context')
            coverage.append(dict(language=r['language'],group=group,edit=edit,covered=bool(ctx is not None and ctx in d.get('syntax_candidates',[]))))
            for method in ('official','syntax','nearest_budget','l1_3','l1_4','delta_dictionary','oracle'):
                score=-d.get('scores',{}).get(method,1.) if d.get('official',{}).get('n_grades',0)>=5 else -float('inf')
                detected=score>tau[r['language'],r['key'],method]
                rows.append(dict(language=r['language'],id=r['id'],key=r['key'],group=group,edit=edit,method=method,detected=detected,
                    joint=bool(detected and q.get('benchmark_pass')),correct=bool(q.get('benchmark_pass')),preserved=bool(q.get('behavior_preserved')),
                    candidates=d.get('candidates',{}).get(method,0)))
df=pd.DataFrame(rows);out=[]
for keys,d in df.groupby(['language','group','edit','method']):
    out.append(dict(zip(('language','group','edit','method'),keys),n=len(d),detected=int(d.detected.sum()),joint_count=int(d.joint.sum()),correct=int(d.correct.sum()),
        preserved=int(d.preserved.sum()),detection=ci(d.groupby('id').detected.mean()),joint=ci(d.groupby('id').joint.mean()),candidates_mean=float(d.candidates.mean())))
cov=pd.DataFrame(coverage).groupby(['language','group','edit']).covered.agg(['sum','count']).reset_index().to_dict('records')
(ROOT/'results/structural_stress_summary.json').write_text(json.dumps(dict(summary=out,coverage=cov,errors=errors),indent=2))
df.to_csv(ROOT/'results/structural_stress_rows.csv',index=False)
print('STRESS_SUMMARY',len(records),'errors',len(errors),flush=True)
for r in out:
    if r['method'] in ('syntax','delta_dictionary','official'):print(r['language'],r['group'],r['edit'],r['method'],r['detected'],r['joint_count'],r['n'],flush=True)
