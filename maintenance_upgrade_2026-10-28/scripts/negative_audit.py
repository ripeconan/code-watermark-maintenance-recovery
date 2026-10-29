"""Use replicated standalone null measurements; never repair positive outcomes."""
import collections,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def supplement(rows,cohort):
    p=ROOT/'results/failed_negative_audit.json'
    if not p.exists():return rows
    groups=collections.defaultdict(list)
    for a in json.loads(p.read_text()):
        if a['cohort']==cohort:groups[a['id'],a['key'],a['group']].append(a)
    for r in rows:
        if 'error' not in r:continue
        for group in ('negative_before','negative_after'):
            aa=groups.get((r['id'],r['key'],group),[])
            if len(aa)!=2 or any('audit_error' in a for a in aa):continue
            x,y=[a['measurement'] for a in aa]
            for name in ('scores','candidates','context','official'):
                assert x.get(name)==y.get(name),('negative audit disagreement',r['id'],group,name)
            r.setdefault('group_scores',{})[group]=x
            r.setdefault('standalone_negative_audit',[]).append(group)
    return rows
