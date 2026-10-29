"""Uniform full-cohort rerun after excluding removed Surefire provider checks."""
import argparse,concurrent.futures,copy,datetime,hashlib,json,re,sys
from pathlib import Path
import test_temporal as base
ROOT=base.ROOT
VERSION='java_v6'
REPOS={'checkstyle/checkstyle','javaparser/javaparser'}

def h(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def is_removed(artifact):
    match=re.fullmatch(r'org\.apache\.maven\.surefire:(surefire-junit4|surefire-junit47):(\d+)\.(\d+)(?:\..*)?',artifact)
    return bool(match and (int(match[2]),int(match[3]))>=(3,6))

def corrected_prepare(work,job):
    assert job['repo'] in REPOS
    identity=job['repo'].replace('/','__')+'__'+job['commit']
    old=ROOT/'records/environments_v4'/(identity+'.json')
    if not old.exists():
        return dict(status='original_preparation_missing',returncode=None,source=str(old)),None
    record=json.loads(old.read_text());failed=[r for r in record.get('provider_warmups',[]) if r.get('status')!='ok']
    removed=[r['artifact'] for r in failed if is_removed(r.get('artifact',''))]
    allow=record.get('returncode')==0 and (record.get('status')=='ok' or (record.get('status')=='provider_dependency_unavailable' and failed and len(removed)==len(failed)))
    result=copy.deepcopy(record)
    result.update(source_preparation_sha256=h(old),source_preparation_file=str(old.relative_to(ROOT)),obsolete_checks_ignored=removed if allow else [],correction_version=VERSION)
    if allow:result['status']='ok'
    folder=ROOT/'records/java_provider_correction_v6';folder.mkdir(exist_ok=True)
    with base.locked(identity):
        target=folder/(identity+'.json')
        if target.exists():assert json.loads(target.read_text())==result
        else:target.write_text(json.dumps(result,indent=2))
    return result,None

def provenance():
    paths=[Path(__file__),ROOT/'scripts/test_temporal.py',ROOT/'scripts/run_project_tests.py',ROOT/'JAVA_PROVIDER_CORRECTION_V6.txt',ROOT/'records/tool_paths.json',ROOT/'records/test_jdk.json']
    paths += [ROOT/'records'/('functional_'+r.replace('/','__')+'.json') for r in sorted(REPOS)]
    return {str(p.relative_to(ROOT)):h(p) for p in paths}

def freeze():
    assert (ROOT/'records/preflight_complete_java_v6.txt').exists()
    rows=[json.loads(s) for s in (ROOT/'results/functional_preflight_java_v6.jsonl').read_text().splitlines() if s]
    plan=json.loads((ROOT/'records/functional_jobs_preflight_java_v6.json').read_text())
    assert {r['job_id'] for r in rows}=={r['job_id'] for r in plan}
    ready={repo:any(r['repo']==repo and r.get('pass_tests') for r in rows) for repo in REPOS}
    result=dict(version=VERSION,ready=all(ready.values()),projects=ready,files=provenance(),created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (ROOT/'records/java_v6_gate.json').write_text(json.dumps(result,indent=2))
    if not result['ready']:
        print('JAVA_V6_PREFLIGHT_REQUIRES_DIAGNOSIS',json.dumps(result),flush=True);raise SystemExit(2)
    (ROOT/'records/java_v6_freeze.json').write_text(json.dumps(result,indent=2))
    print('JAVA_V6_FROZEN',json.dumps(result),flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--preflight',action='store_true');ap.add_argument('--freeze',action='store_true');ap.add_argument('--analyze',action='store_true');a=ap.parse_args()
    if a.freeze:freeze();return
    if a.analyze:
        import analyze_functional_temporal as analysis
        original=analysis.selected_rows
        analysis.selected_rows=lambda:[r for r in original() if r['repo'] in REPOS]
        sys.argv=[sys.argv[0],'--version',VERSION];analysis.main();return
    if not a.preflight:
        saved=json.loads((ROOT/'records/java_v6_freeze.json').read_text())
        assert saved['ready'] and saved['files']==provenance(),'corrected Java recipe changed'
    base.VERSION=VERSION;base.PHASE='preflight' if a.preflight else 'full';base.prepare=corrected_prepare
    jobs=[j for j in base.collect(preflight=a.preflight,original_only=a.preflight) if j['repo'] in REPOS]
    name='functional_preflight_'+VERSION if a.preflight else 'functional_'+VERSION
    out=ROOT/'results'/(name+'.jsonl')
    plan=ROOT/'records'/('functional_jobs_'+('preflight_' if a.preflight else '')+VERSION+'.json')
    plan.write_text(json.dumps([{k:v for k,v in j.items() if k!='code'} for j in jobs],indent=2))
    if not a.preflight:
        old_plan=json.loads((ROOT/'records/functional_jobs_v4_ready.json').read_text())
        identity=lambda j:(j['repo'],j['commit'],j['filename'],j['code_sha256'])
        assert {identity(j) for j in jobs}=={identity(j) for j in old_plan if j['repo'] in REPOS},'changed cohort'
    done={json.loads(s)['job_id'] for s in out.read_text().splitlines() if s} if out.exists() else set()
    remaining=[j for j in jobs if j['job_id'] not in done]
    with out.open('a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures=[executor.submit(base.execute,j) for j in remaining]
        for i,future in enumerate(concurrent.futures.as_completed(futures),1):
            r=future.result();f.write(json.dumps(r)+'\n');f.flush()
            print('JAVA_V6',i,len(remaining),r['repo'],r['status'],r.get('counts'),round(r['total_seconds'],1),flush=True)
    marker='preflight_complete_'+VERSION if a.preflight else 'functional_complete_'+VERSION
    (ROOT/'records'/(marker+'.txt')).write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())
    print('JAVA_V6_PHASE_COMPLETE',name,len(jobs),flush=True)

if __name__=='__main__':main()
