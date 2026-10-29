"""Reused-boundary coverage audit, explicitly exploratory and score-free."""
import json,subprocess,sys,collections,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def one(job):
    from evaluate_upgrade import init
    init()
    from sew.sites.discovery import discover
    from structural_recovery import syntax_candidates
    from structured_candidates import structured,nearest,dictionary
    entries=json.loads((ROOT/'records/development_dictionary.json').read_text()).get(job['language'],[])
    out=[]
    for edit,v in job['variants'].items():
        tree,_,recs=discover(v['code'],job['language'])
        if not recs:
            out.append(dict(edit=edit,error='no_sites'));continue
        c=tuple(map(int,recs[0].sid[-1][4:].split('.')));old=tuple(job['old'])
        sets={'syntax':syntax_candidates(tree,c,job['language']),
              'nearest64':nearest(c,64),'dictionary_pairs64':dictionary(c,entries,combinations=True)}
        for b in (64,128,10**9):sets['structured'+str(b)]=structured(tree,c,job['language'],b)[0]
        out.append(dict(edit=edit,coverage={k:old in s for k,s in sets.items()},candidates={k:len(s) for k,s in sets.items()}))
    return dict(id=job['id'],language=job['language'],key=job['key'],outcomes=out)
def main():
    paths=json.loads((ROOT/'records/tool_paths.json').read_text());base=Path(paths['baseline_scripts']).parent
    old={}
    for line in (base/'results/confirmation_augmented.jsonl').open():
        r=json.loads(line);v=r['groups'].get('positive',{}).get('variants',{}).get('original')
        if v:old[r['id'],r['language'],r['key']]=v['detection']['context']
    out=ROOT/'results/candidate_boundary_audit.jsonl';done=set()
    if out.exists():done={(r['id'],r['language'],r['key']) for s in out.read_text().splitlines() if (r:=json.loads(s))}
    with out.open('a') as f:
        for line in (base/'results/structural_stress_extended.jsonl').open():
            r=json.loads(line);uid=(r['id'],r['language'],r['key'])
            if uid in done:continue
            j={k:r[k] for k in ('id','language','key')};j.update(old=old[uid],variants=r['groups']['positive']['variants'])
            p=subprocess.run([sys.executable,__file__,'--one'],input=json.dumps(j),capture_output=True,text=True,timeout=120)
            try:z=json.loads(p.stdout) if p.returncode==0 else dict(**{k:j[k] for k in ('id','language','key')},error=p.stderr[-1000:])
            except Exception:z=dict(**{k:j[k] for k in ('id','language','key')},error=p.stdout[-1000:])
            f.write(json.dumps(z)+'\n');f.flush()
    rr=[json.loads(s) for s in out.read_text().splitlines()];summary=[]
    for lang in ('python','java','cpp'):
        for edit in ('nested_helper','two_helpers'):
            variants=[x for r in rr if r['language']==lang for x in r.get('outcomes',[]) if x['edit']==edit]
            for method in ('syntax','structured64','structured128','structured1000000000','nearest64','dictionary_pairs64'):
                counts=[x['candidates'][method] for x in variants if 'candidates' in x]
                summary.append(dict(language=lang,edit=edit,method=method,n=72,available=len(counts),covered=sum(x.get('coverage',{}).get(method,False) for x in variants),median_candidates=statistics.median(counts) if counts else None))
    (ROOT/'results/candidate_boundary_summary.json').write_text(json.dumps(dict(records=len(rr),errors=sum('error' in r for r in rr),summary=summary),indent=2));print(json.dumps(summary))
if __name__=='__main__':
    if '--one' in sys.argv:print(json.dumps(one(json.load(sys.stdin))))
    else:main()
