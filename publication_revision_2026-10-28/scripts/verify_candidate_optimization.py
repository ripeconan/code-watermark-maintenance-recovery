"""Check exact candidate equality on every stored confirmation code variant."""
import json
from pathlib import Path
from recovery_probe import init
from structural_recovery import syntax_candidates,syntax_candidates_reference
ROOT=Path(__file__).resolve().parents[1];paths=json.loads((ROOT/'records/tool_paths.json').read_text());init(paths['vendor'])
from sew.sites.discovery import discover
seen=set();n=0
for line in (ROOT/'results/confirmation.jsonl').read_text().split('\n'):
    if not line:continue
    r=json.loads(line)
    for group in r['groups'].values():
        for v in group['variants'].values():
            identity=(r['language'],v['sha256'])
            if identity in seen:continue
            seen.add(identity);tree,_,recs=discover(v['code'],r['language'])
            if not recs:continue
            ctx=tuple(map(int,recs[0].sid[-1][4:].split('.')))
            old=syntax_candidates_reference(tree,ctx,r['language']);new=syntax_candidates(tree,ctx,r['language'])
            assert old==new,(r['id'],r['language'],old,new);n+=1
(ROOT/'records/candidate_optimization_parity.json').write_text(json.dumps(dict(checked_codes=n,unique_codes=len(seen),identical=True)))
print('CANDIDATE_PARITY',n,len(seen),flush=True)
