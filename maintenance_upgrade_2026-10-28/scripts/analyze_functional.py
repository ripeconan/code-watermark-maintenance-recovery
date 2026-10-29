"""Join every preselected source-key attempt to original/marked repository tests."""
import collections,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
METHODS=('official','syntax','structured64','nearest64','dictionary64','dictionary_pairs64')
def main():
    paths=['project_local_tests.jsonl','project_local_tests_sympydeps.jsonl','project_local_tests_javatransport.jsonl','project_local_tests_javaprovider.jsonl','project_local_tests_javabatch.jsonl']
    canonical={};inputs=[]
    for name in paths:
        p=ROOT/'results'/name
        if p.exists():
            inputs.append(name)
            for line in p.read_text().splitlines():
                r=json.loads(line);canonical[r['job_id']]=r
    link={}
    for r in canonical.values():
        for l in r['links']:link[l['id'],l['key'],l['group']]=r
    selected=[r for p in (ROOT/'records').glob('new_functional_*.json') for r in json.loads(p.read_text())]
    decisions={(r['id'],r['key'],r['method']):r for s in (ROOT/'results/project_local_decisions.jsonl').read_text().splitlines() if (r:=json.loads(s))['mode']=='local_paired' and r['alpha']==.05}
    scores={(r['id'],r['key']):r for s in (ROOT/'results/project_local_scores.jsonl').read_text().splitlines() if (r:=json.loads(s))}
    summary=[];detail=[]
    for repo in sorted({r['repo'] for r in selected}):
        rr=[]
        for r in selected:
            if r['repo']!=repo:continue
            for key in (15485863,32452843,49979687):
                tests={g:link.get((r['id'],key,g),{}) for g in ('negative_before','negative_after','positive_before','positive_after')}
                passed={g:x.get('pass_tests',False) for g,x in tests.items()}
                item=dict(repo=repo,id=r['id'],key=key,filename=r['filename'],passed=passed,statuses={g:x.get('status','unavailable') for g,x in tests.items()},
                    original_pair_pass=passed['negative_before'] and passed['negative_after'],all_four_pass=all(passed.values()),
                    after_pair_pass=passed['negative_after'] and passed['positive_after'])
                item['joint']={m:item['all_four_pass'] and decisions[r['id'],key,m]['positive_after'] for m in METHODS}
                item['detection']={m:decisions[r['id'],key,m]['positive_after'] for m in METHODS}
                item['replay_conflict']=scores[r['id'],key].get('merge_status')=='conflict'
                item['missing_original_suite']=any(tests[g].get('status')=='matching_suite_unavailable' for g in ('negative_before','negative_after'))
                item['marked_failure_with_original_pass']=any(passed['negative_'+v] and tests['positive_'+v].get('status') in ('failed','timeout') for v in ('before','after'))
                rr.append(item);detail.append(item)
        jobs=[r for r in canonical.values() if r['repo']==repo]
        summary.append(dict(repo=repo,n=len(rr),files=len(rr)//3,jobs=len(jobs),job_statuses=dict(collections.Counter(r['status'] for r in jobs)),job_pass=sum(r.get('pass_tests',False) for r in jobs),
            original_pair_pass=sum(r['original_pair_pass'] for r in rr),all_four_pass=sum(r['all_four_pass'] for r in rr),after_pair_pass=sum(r['after_pair_pass'] for r in rr),
            missing_original_suite=sum(r['missing_original_suite'] for r in rr),replay_conflict=sum(r['replay_conflict'] for r in rr),
            marked_failure_with_original_pass=sum(r['marked_failure_with_original_pass'] for r in rr),
            detection={m:sum(r['detection'][m] for r in rr) for m in METHODS},
            joint={m:sum(r['joint'][m] for r in rr) for m in METHODS}))
    output=dict(inputs=inputs,summary=summary,detail=detail,
        interpretation='All 8 preselected transitions x 3 keys/project. Joint requires both original versions and both marked versions to pass available repository tests, plus successfully embedded post-maintenance detection. Missing execution is not evidence of functional failure caused by watermarking.')
    (ROOT/'results/functional_summary.json').write_text(json.dumps(output,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
