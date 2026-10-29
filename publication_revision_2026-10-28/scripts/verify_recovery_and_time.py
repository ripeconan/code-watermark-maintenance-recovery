"""Independent single-method parity and timing, on fixed validation carriers."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import hashlib,json,statistics,time,random
from pathlib import Path
from recovery_detector import detect_recovery
from recovery_probe import init
ROOT=Path(__file__).resolve().parents[1]
paths=json.loads((ROOT/'records/tool_paths.json').read_text());init(paths['vendor'])
allrows=[json.loads(s) for s in (ROOT/'results/confirmation_extended.jsonl').read_text().split('\n') if s]
dictionaries=json.loads((ROOT/'records/context_delta_dictionary.json').read_text())['deltas']
rng=random.Random(20261028)
rows=[]
for lang in ('python','java','cpp'):
    eligible=[r for r in allrows if r['language']==lang and r['split']=='valid' and r['key']==15485863]
    eligible.sort(key=lambda r:hashlib.sha256(('timing|'+r['id']).encode()).hexdigest());rows+=eligible[:16]
out=[];budget_mismatches=[];cases=0
for r in allrows:
    for group in r['groups'].values():
        for v in group['variants'].values():
            cs=v['detection']['candidates']
            if cs.get('syntax')!=cs.get('nearest_budget'):budget_mismatches.append(dict(id=r['id'],language=r['language'],counts=cs))
for r in rows:
    key=hashlib.sha256(('confirmation20261028|'+str(r['key'])).encode()).digest()
    for edit in ('original','helper','formatter_helper','helper_loop'):
        v=r['groups']['positive']['variants'].get(edit)
        if not v:continue
        methods=['official','syntax','nearest_budget','l1_1','l1_2','l1_3','l1_4','delta_dictionary'];rng.shuffle(methods)
        for method in methods:
            times=[]
            for repeat in range(3):
                score=detect_recovery(v['code'],r['language'],key,method,deltas=dictionaries[r['language']])
                expected=v['detection']['scores'].get(method,1.)
                assert abs(score['min_p']-expected)<1e-12,(r['id'],method,score,expected)
                assert score['candidates']==v['detection']['candidates'].get(method,0),(r['id'],method)
                times.append(score['seconds']);cases+=1
            out.append(dict(id=r['id'],language=r['language'],edit=edit,method=method,candidates=score['candidates'],
                            grades=score['grades'],median_seconds=statistics.median(times),repeats=times))
(ROOT/'results/recovery_timing.json').write_text(json.dumps(dict(rows=out,parity_cases=cases,budget_mismatches=budget_mismatches),indent=2))
print('PARITY_CASES',cases,'BUDGET_MISMATCHES',len(budget_mismatches),flush=True)
