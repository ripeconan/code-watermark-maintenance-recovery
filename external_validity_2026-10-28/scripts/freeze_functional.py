"""Gate full marked execution on original-only recipe feasibility."""
import argparse,collections,datetime,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='v3'
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    global VERSION
    ap=argparse.ArgumentParser();ap.add_argument('--version',default='v3');ap.add_argument('--allow-partial',action='store_true');a=ap.parse_args();VERSION=a.version
    if (ROOT/'records/functional_hold.txt').exists():
        print('RECIPE_SUPERSEDED_BEFORE_MARKED_EXECUTION',flush=True);raise SystemExit(2)
    assert (ROOT/'records'/f'preflight_complete_{VERSION}.txt').exists()
    rows=[json.loads(s) for s in (ROOT/'results'/f'functional_preflight_{VERSION}.jsonl').read_text().splitlines() if s]
    plan=json.loads((ROOT/'records'/f'functional_jobs_preflight_{VERSION}.json').read_text())
    assert {r['job_id'] for r in rows}=={r['job_id'] for r in plan}
    projects={r['repo'] for r in json.loads((ROOT/'records/acquisition_summary.json').read_text())}
    ready={repo:any(r['repo']==repo and r.get('pass_tests') and r.get('network_isolated') for r in rows) for repo in projects}
    result=dict(version=VERSION,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),ready=all(ready.values()),project_test_execution=ready,preflight_jobs=len(rows),preflight_status=dict(collections.Counter(r['status'] for r in rows)),original_passes=sum(r.get('pass_tests',False) for r in rows),script_sha256=h(ROOT/'scripts/test_temporal.py'),preflight_sha256=h(ROOT/'results'/f'functional_preflight_{VERSION}.jsonl'))
    (ROOT/'records/functional_gate.json').write_text(json.dumps(result,indent=2))
    result['ready_projects']=sorted(repo for repo,ok in ready.items() if ok)
    result['pending_projects']=sorted(repo for repo,ok in ready.items() if not ok)
    if not result['ready'] and not (a.allow_partial and result['ready_projects']):
        print('FUNCTIONAL_ENVIRONMENT_DIAGNOSIS_REQUIRED',json.dumps(result),flush=True)
        raise SystemExit(2)
    paths=[ROOT/'scripts/test_temporal.py',ROOT/'scripts/run_project_tests.py',ROOT/'tools/sandbox_hosts',ROOT/'records/test_jdk.json',ROOT/'records/python313_path.txt',ROOT/'FUNCTIONAL_RECIPE_V1.txt',ROOT/'FUNCTIONAL_AMENDMENT_V2.txt',ROOT/'FUNCTIONAL_AMENDMENT_V3.txt']
    if VERSION=='v4':paths.append(ROOT/'FUNCTIONAL_AMENDMENT_V4.txt')
    if a.allow_partial:paths.extend([ROOT/'FUNCTIONAL_READY_EXECUTION.txt',ROOT/'scripts/test_temporal_v4_preflight.py'])
    result['files']={str(p.relative_to(ROOT)):h(p) for p in paths}
    (ROOT/'records/functional_recipe_freeze.json').write_text(json.dumps(result,indent=2))
    print('FUNCTIONAL_RECIPE_FROZEN',json.dumps(result),flush=True)

if __name__=='__main__':main()
