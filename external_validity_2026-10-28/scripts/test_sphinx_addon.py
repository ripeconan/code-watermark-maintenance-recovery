"""Sphinx-only LuaTeX overlay; isolated from the frozen five-project run."""
import argparse,datetime,hashlib,json,subprocess,sys
from pathlib import Path
import test_temporal as base
ROOT=base.ROOT
VERSION='sphinx_v5'
REPO='sphinx-doc/sphinx'
ORIGINAL_SANDBOX=base.sandbox

def h(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def overlay_sandbox(work,repo,envdir=None,network=False):
    assert repo==REPO
    addon=json.loads((ROOT/'records/sphinx_luatex_addon.json').read_text())
    args=ORIGINAL_SANDBOX(work,repo,envdir,network)
    args+=['--ro-bind',addon['texmf_tree'],'/opt/sphinx-texmf','--setenv','TEXMFHOME','/opt/sphinx-texmf','--setenv','TEXMFCACHE','/tmp/texmf-cache','--dir','/tmp/texmf-cache']
    return args

def provenance():
    files=[Path(__file__),ROOT/'scripts/test_temporal.py',ROOT/'scripts/run_project_tests.py',ROOT/'scripts/prepare_sphinx_luatex.py',ROOT/'SPHINX_ENVIRONMENT_V5.txt',ROOT/'records/sphinx_luatex_addon.json',ROOT/'records/functional_sphinx-doc__sphinx.json']
    return {str(p.relative_to(ROOT)):h(p) for p in files}

def freeze():
    assert (ROOT/'records/preflight_complete_sphinx_v5.txt').exists()
    results=[json.loads(s) for s in (ROOT/'results/functional_preflight_sphinx_v5.jsonl').read_text().splitlines() if s]
    plan=json.loads((ROOT/'records/functional_jobs_preflight_sphinx_v5.json').read_text())
    assert {r['job_id'] for r in results}=={r['job_id'] for r in plan}
    addon=json.loads((ROOT/'records/sphinx_luatex_addon.json').read_text())
    ready=addon['smoke']['status']=='ok' and any(r.get('pass_tests') for r in results)
    data=dict(version=VERSION,ready=ready,preflight_jobs=len(results),original_passes=sum(r.get('pass_tests',False) for r in results),files=provenance(),created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (ROOT/'records/sphinx_v5_gate.json').write_text(json.dumps(data,indent=2))
    if not ready:
        print('SPHINX_ENVIRONMENT_STILL_NEEDS_DIAGNOSIS',json.dumps(data),flush=True);raise SystemExit(2)
    (ROOT/'records/sphinx_recipe_freeze.json').write_text(json.dumps(data,indent=2))
    print('SPHINX_RECIPE_FROZEN',json.dumps(data),flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--preflight',action='store_true');ap.add_argument('--freeze',action='store_true');ap.add_argument('--analyze',action='store_true');a=ap.parse_args()
    if a.freeze:freeze();return
    if a.analyze:
        import analyze_functional_temporal as analysis
        selection=analysis.selected_rows
        analysis.selected_rows=lambda:[r for r in selection() if r['repo']==REPO]
        sys.argv=[sys.argv[0],'--version',VERSION];analysis.main();return
    if not a.preflight:
        frozen=json.loads((ROOT/'records/sphinx_recipe_freeze.json').read_text())
        assert frozen['ready'] and frozen['files']==provenance(),'Sphinx recipe changed'
    base.VERSION=VERSION;base.PHASE='preflight' if a.preflight else 'full';base.sandbox=overlay_sandbox
    jobs=[j for j in base.collect(preflight=a.preflight,original_only=a.preflight) if j['repo']==REPO]
    if a.preflight:
        dates={j['commit']:int(subprocess.check_output(['git','--git-dir',str(ROOT/'data/repos/sphinx-doc__sphinx'),'show','-s','--format=%ct',j['commit']],text=True).strip()) for j in jobs}
        jobs.sort(key=lambda j:(-dates[j['commit']],j['job_id']))
    name='functional_preflight_'+VERSION if a.preflight else 'functional_'+VERSION
    out=ROOT/'results'/(name+'.jsonl')
    plan=ROOT/'records'/('functional_jobs_'+('preflight_' if a.preflight else '')+VERSION+'.json')
    plan.write_text(json.dumps([{k:v for k,v in j.items() if k!='code'} for j in jobs],indent=2))
    done={json.loads(s)['job_id'] for s in out.read_text().splitlines() if s} if out.exists() else set()
    remaining=[j for j in jobs if j['job_id'] not in done]
    with out.open('a') as f:
        for i,job in enumerate(remaining,1):
            result=base.execute(job)
            f.write(json.dumps(result)+'\n');f.flush()
            print('SPHINX_TEST',i,len(remaining),result['status'],result.get('counts'),round(result['total_seconds'],1),flush=True)
    marker='preflight_complete_'+VERSION if a.preflight else 'functional_complete_'+VERSION
    (ROOT/'records'/(marker+'.txt')).write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())
    print('SPHINX_PHASE_COMPLETE',name,len(jobs),flush=True)

if __name__=='__main__':main()
