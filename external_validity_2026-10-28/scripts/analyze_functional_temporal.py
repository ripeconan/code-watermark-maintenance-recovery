"""Functional outcomes with every preselected transition/key in denominators."""
import argparse,collections,json
from pathlib import Path
from test_temporal import selected_rows
ROOT=Path(__file__).resolve().parents[1]
METHODS=('official','syntax','structured64','nearest64','dictionary64','dictionary_pairs64')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--version',default='v2');ap.add_argument('--ready-only',action='store_true');a=ap.parse_args()
    tag=a.version+('_ready' if a.ready_only else '')
    rows=selected_rows()
    pending=[]
    if a.ready_only:
        freeze=json.loads((ROOT/'records/functional_recipe_freeze.json').read_text());pending=freeze['pending_projects']
        rows=[r for r in rows if r['repo'] in freeze['ready_projects']]
    results=[json.loads(s) for s in (ROOT/'results'/f'functional_{tag}.jsonl').read_text().splitlines() if s]
    jobs=json.loads((ROOT/'records'/f'functional_jobs_{tag}.json').read_text())
    assert len({r['job_id'] for r in results})==len(results)
    assert {r['job_id'] for r in results}=={r['job_id'] for r in jobs},'functional cohort incomplete'
    # Preserve the complete final plan's links even when result records are reused.
    tested={r['job_id']:r for r in results};links={}
    for job in jobs:
        for link in job['links']:links[link['id'],link['key'],link['group']]=tested[job['job_id']]
    decisions={}
    for line in (ROOT/'results/temporal_decisions.jsonl').read_text().splitlines():
        r=json.loads(line)
        if r['mode']=='earlier_paired' and r['alpha']==.05 and r['method'] in METHODS:
            decisions[r['id'],r['key'],r['method']]=r
    scores={(r['id'],r['key']):r for line in (ROOT/'results/temporal_scores.jsonl').read_text().splitlines() if line and (r:=json.loads(line))}
    detailed=[]
    for row in rows:
        for key in (15485863,32452843,49979687):
            groups={g:links.get((row['id'],key,g)) for g in ('negative_before','negative_after','positive_before','positive_after')}
            passed={g:bool(r and r.get('pass_tests')) for g,r in groups.items()}
            original=passed['negative_before'] and passed['negative_after'];allfour=all(passed.values())
            score=scores[row['id'],key]
            regression=any(passed['negative_'+suffix] and groups['positive_'+suffix] and not passed['positive_'+suffix] for suffix in ('before','after'))
            detailed.append(dict(id=row['id'],repo=row['repo'],filename=row['filename'],sha=row['sha'],key=key,original_pair_passed=original,all_four_passed=allfour,marked_failed_when_original_passed=bool(regression),embedding_ok=score.get('embedding',{}).get('status')=='ok',merge_status=score.get('merge_status','not_completed'),status={g:r['status'] if r else 'version_not_produced' for g,r in groups.items()},joint_detection_and_tests={method:allfour and decisions[row['id'],key,method]['positive_after'] for method in METHODS}))
    summary=[]
    for repo in sorted({r['repo'] for r in detailed}):
        rr=[r for r in detailed if r['repo']==repo]
        summary.append(dict(repo=repo,planned_transitions=len({r['id'] for r in rr}),distinct_paths=len({r['filename'] for r in rr}),source_key_attempts=len(rr),**{g:sum(r[g] for r in rr) for g in ('original_pair_passed','all_four_passed','marked_failed_when_original_passed','embedding_ok')},joint_detection_and_tests={m:sum(r['joint_detection_and_tests'][m] for r in rr) for m in METHODS},merge_status=dict(collections.Counter(r['merge_status'] for r in rr))))
    output=dict(recipe_version=a.version,partial_project_stage=a.ready_only,pending_projects=pending,pending_selected_transitions=sum(r['repo'] in pending for r in selected_rows()),unique_test_jobs=len(results),job_status=dict(collections.Counter(r['status'] for r in results)),summary=summary,interpretation='All preselected transitions/keys of the explicitly listed projects retained. Pending projects have no final functional result. Test failure after original pass is an observed regression, not by itself causal proof. Whole-suite test passage is not semantic equivalence.')
    (ROOT/'results'/f'functional_summary_{tag}.json').write_text(json.dumps(output,indent=2))
    with (ROOT/'results'/f'functional_decisions_{tag}.jsonl').open('w') as f:
        for r in detailed:f.write(json.dumps(r)+'\n')
    print(json.dumps(output,indent=2),flush=True)

if __name__=='__main__':main()
