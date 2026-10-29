"""Final ledger, frozen-recipe and cross-version checks without re-running tests."""
import datetime,json,hashlib,collections
from pathlib import Path
from summarize_functional_final import STAGES,rows
ROOT=Path(__file__).resolve().parents[1]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    final=json.loads((ROOT/'results/functional_summary_final.json').read_text())
    assert final['selected_transitions']==144 and final['source_key_attempts']==432 and final['unique_test_jobs']==966
    assert final['distinct_project_paths']==87
    assert all(digest(ROOT/name)==expected for name,expected in final['sources_sha256'].items())
    frozen_checks={}
    for name in ('sphinx_recipe_freeze.json','rich_v7_freeze.json','java_v8_freeze.json'):
        frozen=json.loads((ROOT/'records'/name).read_text());assert frozen['ready']
        assert all(digest(ROOT/path)==value for path,value in frozen['files'].items()),name
        frozen_checks[name]=len(frozen['files'])
    earlier=json.loads((ROOT/'records/functional_recipe_freeze.json').read_text())
    assert earlier['script_sha256']==digest(ROOT/'scripts/test_temporal.py')
    jobs=[r for tag,repos in STAGES.items() for r in rows(ROOT/'results'/('functional_'+tag+'.jsonl')) if r['repo'] in repos]
    assert len(jobs)==len({r['job_id'] for r in jobs})==966
    assert all(bool(r.get('pass_tests'))==(r['status']=='ok') for r in jobs),'process success differs from full-suite passage'
    detailed=rows(ROOT/'results/functional_decisions_final.jsonl')
    assert len(detailed)==len({(r['id'],r['key']) for r in detailed})==432
    assert all(not r['all_four_passed'] or r['original_pair_passed'] for r in detailed)
    assert all(not any(r['joint_detection_and_tests'].values()) or r['all_four_passed'] for r in detailed)
    for project in final['summary']:
        rr=[r for r in detailed if r['repo']==project['repo']]
        assert len(rr)==72
        for name in ('original_pair_passed','all_four_passed','marked_failed_when_original_passed'):
            assert sum(r[name] for r in rr)==project[name]
        for method,count in project['joint_detection_and_tests'].items():
            assert sum(r['joint_detection_and_tests'][method] for r in rr)==count
    report=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        verified=True,frozen_recipe_files_checked=frozen_checks,canonical_jobs=len(jobs),
        original_jobs=sum(r['original'] for r in jobs),marked_jobs=sum(not r['original'] for r in jobs),
        job_status=dict(collections.Counter(r['status'] for r in jobs)),transition_key_attempts=len(detailed),
        original_pair_passed=sum(r['original_pair_passed'] for r in detailed),all_four_passed=sum(r['all_four_passed'] for r in detailed),
        java_previously_tested_pass_status_changed=final['java_correction']['previously_tested_pass_status_changed'],
        rich_old_passed_now_failed=final['rich_correction']['old_passed_now_failed'],
        remaining_review=bool(final['java_correction']['previously_tested_pass_status_changed'] or final['rich_correction']['old_passed_now_failed']),
        final_summary_sha256=digest(ROOT/'results/functional_summary_final.json'))
    (ROOT/'records/functional_final_verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()
