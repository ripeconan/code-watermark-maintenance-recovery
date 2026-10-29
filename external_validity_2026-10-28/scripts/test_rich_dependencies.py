"""Uniform Rich rerun with a missing historical test dependency restored."""
import argparse,concurrent.futures,datetime,hashlib,json,subprocess,sys
from pathlib import Path
import test_temporal as base
ROOT=base.ROOT
VERSION='rich_v7'
REPO='Textualize/rich'

def h(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare(work,job):
    assert job['repo']==REPO
    identity=REPO.replace('/','__')+'__'+job['commit']
    old=ROOT/'records/environments_v4'/(identity+'.json')
    old_freeze=old.with_suffix('.freeze.txt')
    folder=ROOT/'records/environments_rich_v7';folder.mkdir(exist_ok=True)
    envdir=ROOT/'tools/envs_rich_v7'/identity
    with base.locked(identity):
        target=folder/(identity+'.json')
        if target.exists():return json.loads(target.read_text()),envdir
        before=json.loads(old.read_text())
        if before['status']!='ok':
            return dict(status='original_preparation_unavailable',source=str(old)),envdir
        original={s.strip() for s in old_freeze.read_text().splitlines() if s.strip()}
        assert not any(s.lower().startswith('setuptools') for s in original),'unexpected old setuptools pin'
        deps=sorted(original)+['setuptools==75.8.0']
        envdir.parent.mkdir(exist_ok=True)
        uv=str(ROOT/'tools/bootstrap/bin/uv')
        subprocess.run([uv,'venv','--python',str(base.PY311/'bin/python'),'--no-project',str(envdir)],capture_output=True,text=True,check=True,timeout=60)
        command=['/opt/uv','pip','install','--python',str(envdir/'bin/python'),'--index-url','https://pypi.tuna.tsinghua.edu.cn/simple',*deps]
        logdir=ROOT/'logs'/('functional_'+VERSION+'_'+base.PHASE);logdir.mkdir(exist_ok=True)
        result=base.run_limited(base.sandbox(work,REPO,envdir,network=True)+command,work,logdir/(identity+'_prepare.log'),timeout=900)
        if result['status']=='ok':
            p=subprocess.run([uv,'pip','freeze','--python',str(envdir/'bin/python')],capture_output=True,text=True,check=True,timeout=60)
            frozen={s.strip() for s in p.stdout.splitlines() if s.strip()}
            assert frozen==original|{'setuptools==75.8.0'},'dependency changes beyond the declared correction'
            (folder/(identity+'.freeze.txt')).write_text(p.stdout)
        result.update(requirements=deps,environment=str(envdir),command=command,original_snapshot=True,recipe_version=VERSION,
            source_preparation_sha256=h(old),source_freeze_sha256=h(old_freeze))
        target.write_text(json.dumps(result,indent=2))
        return result,envdir

def provenance():
    paths=[Path(__file__),ROOT/'scripts/test_temporal.py',ROOT/'scripts/run_project_tests.py',ROOT/'RICH_DEPENDENCY_CORRECTION_V7.txt',ROOT/'records/functional_Textualize__rich.json']
    paths+=sorted((ROOT/'records/environments_v4').glob('Textualize__rich__*.freeze.txt'))
    return {str(p.relative_to(ROOT)):h(p) for p in paths}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--preflight',action='store_true');ap.add_argument('--freeze',action='store_true');ap.add_argument('--analyze',action='store_true');a=ap.parse_args()
    if a.analyze:
        import analyze_functional_temporal as analysis
        original=analysis.selected_rows;analysis.selected_rows=lambda:[r for r in original() if r['repo']==REPO]
        sys.argv=[sys.argv[0],'--version',VERSION];analysis.main();return
    if a.freeze:
        assert (ROOT/'records'/('preflight_complete_'+VERSION+'.txt')).exists()
        rr=[json.loads(s) for s in (ROOT/'results'/('functional_preflight_'+VERSION+'.jsonl')).read_text().splitlines() if s]
        plan=json.loads((ROOT/'records'/('functional_jobs_preflight_'+VERSION+'.json')).read_text())
        assert len(rr)==len(plan) and {r['job_id'] for r in rr}=={r['job_id'] for r in plan}
        assert any(r.get('pass_tests') for r in rr),'Rich corrected environment needs diagnosis'
        frozen=dict(ready=True,version=VERSION,files=provenance(),created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        (ROOT/'records'/(VERSION+'_freeze.json')).write_text(json.dumps(frozen,indent=2));print('RICH_V7_FROZEN',flush=True);return
    if not a.preflight:
        frozen=json.loads((ROOT/'records'/(VERSION+'_freeze.json')).read_text());assert frozen['ready'] and frozen['files']==provenance()
    base.VERSION=VERSION;base.PHASE='preflight' if a.preflight else 'full';base.prepare=prepare
    jobs=[j for j in base.collect(preflight=a.preflight,original_only=a.preflight) if j['repo']==REPO]
    if not a.preflight:
        old=json.loads((ROOT/'records/functional_jobs_v4_ready.json').read_text())
        identity=lambda j:(j['repo'],j['commit'],j['filename'],j['code_sha256'])
        assert {identity(j) for j in jobs}=={identity(j) for j in old if j['repo']==REPO}
    suffix=('preflight_' if a.preflight else '')+VERSION
    (ROOT/'records'/('functional_jobs_'+suffix+'.json')).write_text(json.dumps([{k:v for k,v in j.items() if k!='code'} for j in jobs],indent=2))
    out=ROOT/'results'/('functional_'+suffix+'.jsonl')
    done={json.loads(s)['job_id'] for s in out.read_text().splitlines() if s} if out.exists() else set()
    pending=[j for j in jobs if j['job_id'] not in done]
    with out.open('a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        for i,future in enumerate(concurrent.futures.as_completed([ex.submit(base.execute,j) for j in pending]),1):
            r=future.result();f.write(json.dumps(r)+'\n');f.flush()
            print('RICH_V7',i,len(pending),r['status'],r.get('counts'),round(r['total_seconds'],1),flush=True)
    (ROOT/'records'/(('preflight' if a.preflight else 'functional')+'_complete_'+VERSION+'.txt')).write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())

if __name__=='__main__':main()
