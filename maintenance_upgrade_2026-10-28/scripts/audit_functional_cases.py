"""Reproduce conditional development counts and locate observed regressions."""
import json,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    dev=[json.loads(s) for s in (ROOT/'results/project_tests_lf.jsonl').read_text().splitlines()]
    dev=[r for r in dev if r['repo']=='mahmoud/boltons']
    # Development executes a full repository suite: unmodified jobs were
    # deduplicated by repository/revision, regardless of nominated source file.
    original={(r['repo'],r['commit']):r for r in dev if all(l['group'].startswith('negative') for l in r['links'])}
    marked=[r for r in dev if any(l['group'].startswith('positive') for l in r['links'])]
    eligible=[r for r in marked if original.get((r['repo'],r['commit']),{}).get('pass_tests')]
    failures=[{k:r[k] for k in ('job_id','filename','commit','links','log_tail')} for r in eligible if not r['pass_tests']]
    nx=[json.loads(s) for s in (ROOT/'results/project_local_tests.jsonl').read_text().splitlines()]
    nx=[r for r in nx if r['repo']=='networkx/networkx']
    orig={(r['commit'],r['filename']):r for r in nx if all(l['group'].startswith('negative') for l in r['links'])}
    nxfailed=[]
    for r in nx:
        if r['status']=='failed' and any(l['group'].startswith('positive') for l in r['links']):
            nxfailed.append({k:r[k] for k in ('job_id','filename','commit','links','log_tail')}|dict(original_pass=orig[r['commit'],r['filename']]['pass_tests']))
    result=dict(boltons=dict(total_jobs=len(dev),original_jobs=len(original),marked_jobs=len(marked),conditional_marked_jobs=len(eligible),conditional_pass=sum(r['pass_tests'] for r in eligible),failures=failures),networkx_failures=nxfailed)
    assert len(eligible)==78 and sum(r['pass_tests'] for r in eligible)==76,(len(eligible),sum(r['pass_tests'] for r in eligible),len(original),len(marked),len(dev))
    assert len(nxfailed)==2 and all(r['original_pass'] for r in nxfailed)
    (ROOT/'results/functional_case_audit.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result['boltons'].items() if k!='failures'}))
if __name__=='__main__':main()
