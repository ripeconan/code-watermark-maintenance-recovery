"""Combine complete, uniformly corrected project cohorts without outcome selection."""
import collections, datetime, hashlib, json
from pathlib import Path
from test_temporal import selected_rows

ROOT=Path(__file__).resolve().parents[1]
STAGES={
    'v4_ready':{'pallets/flask','apache/commons-csv'},
    'java_v8':{'checkstyle/checkstyle','javaparser/javaparser'},
    'sphinx_v5':{'sphinx-doc/sphinx'},
    'rich_v7':{'Textualize/rich'},
}
MARKERS={'v4_ready':'functional_ready_analysis_complete.txt',
         'java_v8':'java_v8_analysis_complete.txt',
         'sphinx_v5':'sphinx_v5_analysis_complete.txt',
         'rich_v7':'rich_v7_analysis_complete.txt'}

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]

def identity(job):
    return job['repo'],job['commit'],job['filename'],job['code_sha256']

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    sources={};details=[];jobs=[];summaries=[]
    for stage,repos in STAGES.items():
        assert (ROOT/'records'/MARKERS[stage]).exists(),stage+' has not completed analysis'
        paths={name:ROOT/'results'/f'functional_{name}_{stage}.{ext}' for name,ext in [('summary','json'),('decisions','jsonl')]}
        result_path=ROOT/'results'/f'functional_{stage}.jsonl'
        plan_path=ROOT/'records'/f'functional_jobs_{stage}.json'
        result=rows(result_path);plan=json.loads(plan_path.read_text())
        assert len(result)==len({r['job_id'] for r in result})==len(plan)
        assert {r['job_id'] for r in result}=={r['job_id'] for r in plan}
        jobs.extend(dict(r,canonical_stage=stage) for r in result if r['repo'] in repos)
        details.extend(dict(r,canonical_stage=stage) for r in rows(paths['decisions']) if r['repo'] in repos)
        summaries.extend(dict(r,canonical_stage=stage) for r in json.loads(paths['summary'].read_text())['summary'] if r['repo'] in repos)
        for path in [*paths.values(),result_path,plan_path]:sources[str(path.relative_to(ROOT))]=digest(path)
    selected=selected_rows()
    expected={(r['id'],key) for r in selected for key in (15485863,32452843,49979687)}
    assert len(details)==len({(r['id'],r['key']) for r in details})
    assert {(r['id'],r['key']) for r in details}==expected
    assert len(selected)==144 and len(details)==432
    assert len({identity(r) for r in jobs})==len(jobs)==966
    assert len(summaries)==6
    for summary in summaries:
        assert summary['planned_transitions']==24 and summary['source_key_attempts']==72
        denominator=summary['original_pair_passed']
        summary['all_four_given_original_pair_passed']=summary['all_four_passed']/denominator if denominator else None
        summary['all_four_over_all_preselected']=summary['all_four_passed']/summary['source_key_attempts']
    corrected_repos=STAGES['java_v8']|STAGES['rich_v7']
    old={identity(r):r for r in rows(ROOT/'results/functional_v4_ready.jsonl') if r['repo'] in corrected_repos}
    new={identity(r):r for r in jobs if r['repo'] in corrected_repos}
    assert old.keys()==new.keys()
    audit=[]
    for ident,before in old.items():
        after=new[ident]
        audit.append(dict(repo=ident[0],commit=ident[1],filename=ident[2],code_sha256=ident[3],
            original=before['original'],old_job_id=before['job_id'],new_job_id=after['job_id'],
            old_status=before['status'],new_status=after['status'],
            old_passed=bool(before.get('pass_tests')),new_passed=bool(after.get('pass_tests')),
            previously_tested=before['status']!='original_environment_unavailable'))
    java=[r for r in audit if r['repo'] in STAGES['java_v8']]
    retested=[r for r in java if r['previously_tested']]
    changed=[r for r in retested if r['old_passed']!=r['new_passed']]
    rich=[r for r in audit if r['repo'] in STAGES['rich_v7']]
    output=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        canonical_project_stages={k:sorted(v) for k,v in STAGES.items()},
        selected_transitions=len(selected),distinct_project_paths=len({(r['repo'],r['filename']) for r in details}),
        source_key_attempts=len(details),unique_test_jobs=len(jobs),
        job_status=dict(collections.Counter(r['status'] for r in jobs)),summary=sorted(summaries,key=lambda r:r['repo']),
        java_correction=dict(total_jobs=len(java),previously_tested=len(retested),
            old_unavailable=sum(not r['previously_tested'] for r in java),
            old_unavailable_now_passed=sum(not r['previously_tested'] and r['new_passed'] for r in java),
            previously_tested_pass_status_changed=len(changed),changed=changed),
        rich_correction=dict(total_jobs=len(rich),
            old_failed_now_passed=sum(not r['old_passed'] and r['new_passed'] for r in rich),
            old_passed_now_failed=sum(r['old_passed'] and not r['new_passed'] for r in rich)),
        sources_sha256=sources,
        interpretation='All 144 preselected transitions and all three keys are retained. Keys are repeated evaluations, not independent samples. Canonical stages are chosen per project by the documented environment correction, never per-result outcome. All original observations remain available. Whole-suite passage is not semantic equivalence; original-failing pairs are inconclusive for watermark-induced regressions. Conditional test passage and unconditional end-to-end yield must both be reported. Any changed outcome among previously tested Java code requires review before manuscript integration.')
    (ROOT/'results/functional_summary_final.json').write_text(json.dumps(output,indent=2))
    for name,data in [('functional_decisions_final',details),('java_v4_v8_comparison',java),('rich_v4_v7_comparison',rich)]:
        with (ROOT/'results'/(name+'.jsonl')).open('w') as f:
            for row in data:f.write(json.dumps(row)+'\n')
    (ROOT/'records/functional_final_analysis_complete.txt').write_text(output['created_utc'])
    print(json.dumps(output,indent=2),flush=True)

if __name__=='__main__':main()
