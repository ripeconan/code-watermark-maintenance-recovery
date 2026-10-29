"""Prospectively selected module/full-core tests; unavailable cases stay visible."""
import argparse,gzip,hashlib,json,os,subprocess,tempfile,time
from pathlib import Path
from run_project_tests import safe_extract,base_sandbox,run_limited,xml_counts,maven_args
ROOT=Path(__file__).resolve().parents[1]
PYBASE='/home2/icdm/conda_envs/aaai27'
RUN_ID=None

def collect():
    selected={r['id'] for p in (ROOT/'records').glob('new_functional_*.json') for r in json.loads(p.read_text())}
    raw={r['id']:r for p in (ROOT/'data/project_calibration').glob('*.json.gz') if '.frame.' not in p.name for r in json.loads(gzip.decompress(p.read_bytes())) if r['id'] in selected}
    scores={(r['id'],r['key']):r for s in (ROOT/'results/project_local_scores.jsonl').read_text().splitlines() if s and (r:=json.loads(s)) and r['id'] in selected}
    jobs={}
    for uid,row in raw.items():
        for key in (15485863,32452843,49979687):
            r=scores.get((uid,key),{});codes={'negative_before':row['before'],'negative_after':row['after']}
            if r.get('codes_file'):codes.update(json.loads(gzip.decompress((ROOT/r['codes_file']).read_bytes())))
            for group,code in codes.items():
                commit=row['parent_sha'] if group.endswith('before') else row['sha'];negative=group.startswith('negative')
                ch=hashlib.sha256(code.encode()).hexdigest();identity=(row['repo'],commit,row['filename'],'' if negative else ch,'local-functional-v2')
                jid=hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
                j=jobs.setdefault(jid,dict(job_id=jid,repo=row['repo'],language=row['language'],commit=commit,filename=row['filename'],code=None if negative else code,code_sha256=ch,links=[]))
                j['links'].append(dict(id=uid,key=key,group=group))
    return sorted(jobs.values(),key=lambda j:(j['language']!='python',j['repo'],j['commit'],j['code'] is not None,j['job_id']))

def test(job,paths):
    archive=ROOT/'data/project_snapshots_lf'/f"{job['repo'].replace('/','__')}__{job['commit']}.tar.gz"
    if not archive.exists():return dict(status='snapshot_unavailable',pass_tests=False)
    logdir=ROOT/'logs'/('project_local_tests' if not RUN_ID else 'project_local_tests_'+RUN_ID);logdir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='local-test-',dir=ROOT/'work') as tmp:
        work=Path(tmp);safe_extract(archive,work)
        if job['language']=='python':
            src=Path(job['filename']);suite=src.parent/'tests'/('test_'+src.stem+'.py')
            if not (work/suite).is_file():return dict(status='matching_suite_unavailable',pass_tests=False,suite=str(suite))
        else:
            stamp=ROOT/'tools/warmups_v2'/f"{job['repo'].replace('/','__')}__{job['commit']}.json";stamp.parent.mkdir(exist_ok=True)
            if not stamp.exists():
                # Exact original revision, only dependency/compile preparation;
                # actual tests execute subsequently with no network.
                cmd=[str(ROOT/'tools/apache-maven-3.9.11/bin/mvn'),*[x for x in maven_args(job['repo']) if x!='-q'],
                    '-Daether.connector.http.requestTimeout=30000','-Daether.connector.http.connectTimeout=10000',
                    f'-Dmaven.repo.local={ROOT / "tools/m2"}','-DskipTests=true','test']
                # Keep harness files outside the repository: Apache RAT scans
                # untracked files as well as source, so an injected helper script
                # would contaminate the original project's license check.
                shell=ROOT/'work'/('_prepare_'+job['job_id']+'.sh')
                import shlex
                shell.write_text('export JAVA_HOME='+shlex.quote(paths['jdk'])+'\nexport MAVEN_OPTS="-Xmx1536m -XX:ActiveProcessorCount=1 -Djava.net.preferIPv4Stack=true"\nexec '+shlex.join(cmd)+'\n')
                warm=run_limited(['bash',str(shell)],work,logdir/(job['job_id']+'_prepare.log'),timeout=600)
                shell.unlink(missing_ok=True)
                stamp.write_text(json.dumps(warm,indent=2))
            warm=json.loads(stamp.read_text())
            if warm.get('returncode')!=0:return dict(status='dependency_or_build_unavailable',pass_tests=False,preparation=warm)
        if job['code'] is not None:(work/job['filename']).write_bytes(job['code'].encode())
        sandbox=base_sandbox(work,paths)
        if job['language']=='python':
            sandbox+=['--ro-bind',PYBASE,PYBASE,'--setenv','PYTHONPATH','/work:/work/src:/opt/test_packages']
            package=job['filename'].split('/')[0]
            args=['-q','--disable-warnings','--maxfail=3','--junitxml=/work/_cwm_junit.xml',suite.as_posix()]
            code='import '+package+'; assert '+package+'.__file__.startswith("/work/"), '+package+'.__file__; import pytest; raise SystemExit(pytest.main('+repr(args)+'))'
            command=[PYBASE+'/bin/python','-c',code]
        else:
            sandbox+=['--ro-bind',str(ROOT/'tools/apache-maven-3.9.11'),'/opt/maven','--bind',str(ROOT/'tools/m2'),'/cache/m2',
                '--setenv','JAVA_HOME','/opt/jdk','--setenv','MAVEN_OPTS','-Xmx1536m -XX:ActiveProcessorCount=1']
            if job['repo']=='apache/commons-lang':
                # This sandbox has no passwd database. Give all Java processes
                # the same existing home as HOME, including Surefire's forks.
                sandbox+=['--setenv','JAVA_TOOL_OPTIONS','-Duser.home=/tmp']
            command=['/opt/maven/bin/mvn',*maven_args(job['repo']),'-o','-Dmaven.repo.local=/cache/m2','test'];suite='full-core-project'
        log=logdir/(job['job_id']+'.log');result=run_limited(sandbox+command,work,log,timeout=240)
        xmls=[work/'_cwm_junit.xml'] if job['language']=='python' else list(work.rglob('surefire-reports/TEST-*.xml'))
        counts=xml_counts([p for p in xmls if p.exists()]);result.update(counts=counts,command=command,suite=str(suite),network_isolated=True,
            pass_tests=result['status']=='ok' and counts['tests']>counts['skipped'] and counts['failures']==0 and counts['errors']==0,log=str(log.relative_to(ROOT)))
        return result

def main():
    global RUN_ID
    ap=argparse.ArgumentParser();ap.add_argument('--language');ap.add_argument('--limit',type=int);ap.add_argument('--repository');ap.add_argument('--run-id');a=ap.parse_args();RUN_ID=a.run_id
    paths=json.loads((ROOT/'records/tool_paths.json').read_text());out=ROOT/'results'/('project_local_tests.jsonl' if not RUN_ID else 'project_local_tests_'+RUN_ID+'.jsonl')
    done={json.loads(s)['job_id'] for s in out.read_text().splitlines() if s} if out.exists() else set()
    jobs=[j for j in collect() if j['job_id'] not in done and (not a.language or j['language']==a.language) and (not a.repository or j['repo']==a.repository)]
    if a.limit:jobs=jobs[:a.limit]
    with out.open('a') as f:
        for i,j in enumerate(jobs,1):
            start=time.time()
            try:r=test(j,paths)
            except Exception as e:r=dict(status='harness_error',pass_tests=False,error=type(e).__name__+': '+str(e))
            f.write(json.dumps({k:v for k,v in j.items() if k!='code'}|r|dict(total_seconds=time.time()-start))+'\n');f.flush()
            print('LOCAL_TEST',i,len(jobs),j['repo'],r['status'],r.get('counts'),round(time.time()-start,1),flush=True)

if __name__=='__main__':main()
