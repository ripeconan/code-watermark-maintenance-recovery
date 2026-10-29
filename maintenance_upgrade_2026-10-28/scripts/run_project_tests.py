"""Execute original/marked/replayed projects in a network-isolated sandbox."""
import argparse,gzip,hashlib,json,os,resource,signal,subprocess,tarfile,tempfile,time,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def safe_extract(archive,dest):
    with tarfile.open(archive,'r:gz') as tf:tf.extractall(dest,filter='data')

def maven_args(repo):
    args=['-B','-q','-Dstyle.color=never','-Dcheckstyle.skip=true','-Dspotless.skip=true','-Denforcer.skip=true','-Dmaven.javadoc.skip=true','-Djacoco.skip=true']
    if repo=='google/gson':args+=['-pl','gson','-am']
    return args

def base_sandbox(work,paths):
    args=['bwrap','--ro-bind','/usr','/usr','--ro-bind','/lib','/lib','--ro-bind','/lib64','/lib64',
        '--ro-bind','/etc/alternatives','/etc/alternatives','--symlink','usr/bin','/bin',
        '--proc','/proc','--dev','/dev','--tmpfs','/tmp','--bind',str(work),'/work',
        '--ro-bind',str(ROOT/'tools/test_packages'),'/opt/test_packages','--ro-bind',paths['jdk'],'/opt/jdk',
        '--chdir','/work','--unshare-all','--die-with-parent','--new-session','--clearenv',
        '--setenv','PATH','/usr/bin:/bin:/opt/jdk/bin:/opt/maven/bin','--setenv','HOME','/tmp',
        '--setenv','LANG','C.UTF-8','--setenv','LC_ALL','C.UTF-8','--setenv','PYTHONHASHSEED','0',
        '--setenv','PYTHONPATH','/opt/test_packages:/work:/work/src','--setenv','PYTEST_DISABLE_PLUGIN_AUTOLOAD','1',
        '--setenv','OPENBLAS_NUM_THREADS','1','--setenv','OMP_NUM_THREADS','1']
    return args

def run_limited(cmd,work,log,timeout=240):
    def limits():
        resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_CPU,(timeout,timeout+5))
        resource.setrlimit(resource.RLIMIT_FSIZE,(128*1024**2,128*1024**2))
    start=time.time()
    with log.open('wb') as output:
        p=subprocess.Popen(cmd,cwd=work,stdout=output,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits)
        try:p.wait(timeout=timeout);status='ok' if p.returncode==0 else 'failed'
        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait();status='timeout'
    return dict(status=status,returncode=p.returncode,seconds=time.time()-start,log_tail=log.read_text(errors='replace')[-3500:])

def xml_counts(paths):
    totals=dict(tests=0,failures=0,errors=0,skipped=0,xml_files=0)
    for p in paths:
        try:
            tree=ET.parse(p).getroot();suites=[tree] if tree.tag=='testsuite' else list(tree.iter('testsuite'))
            for s in suites:
                for k in ('tests','failures','errors','skipped'):totals[k]+=int(s.get(k,0))
            totals['xml_files']+=1
        except (ET.ParseError,ValueError):pass
    return totals

def test_job(job,paths):
    archive=ROOT/'data/project_snapshots_lf'/f"{job['repo'].replace('/','__')}__{job['commit']}.tar.gz"
    if not archive.exists():return dict(status='snapshot_unavailable',pass_tests=False)
    logdir=ROOT/'logs/project_tests';logdir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='project-test-',dir=ROOT/'work') as tmp:
        work=Path(tmp);safe_extract(archive,work)
        if job['language']=='java':
            # Resolve public Maven dependencies on an unmodified original source
            # before any scored execution. Actual test runs are offline/sandboxed.
            stamp=ROOT/'tools/warmups'/f"{job['repo'].replace('/','__')}__{job['commit']}.json"
            if not stamp.exists():
                stamp.parent.mkdir(exist_ok=True);m2=ROOT/'tools/m2';m2.mkdir(exist_ok=True)
                env={**os.environ,'JAVA_HOME':paths['jdk'],'MAVEN_OPTS':'-Xmx1536m -XX:ActiveProcessorCount=2'}
                cmd=[str(ROOT/'tools/apache-maven-3.9.11/bin/mvn'),*maven_args(job['repo']),f'-Dmaven.repo.local={m2}','dependency:go-offline','-DskipTests=true']
                log=logdir/(job['job_id']+'_dependencies.log')
                with log.open('wb') as output:
                    try:
                        p=subprocess.run(cmd,cwd=work,env=env,stdout=output,stderr=subprocess.STDOUT,timeout=300)
                        warm=dict(returncode=p.returncode,log_tail=log.read_text(errors='replace')[-2000:])
                    except subprocess.TimeoutExpired:warm=dict(returncode=None,error='dependency_timeout')
                stamp.write_text(json.dumps(warm,indent=2))
            warm=json.loads(stamp.read_text())
            if warm.get('returncode')!=0:return dict(status='dependency_unavailable',pass_tests=False,dependency=warm)
        if job.get('code') is not None:
            p=(work/job['filename']).resolve()
            if work.resolve() not in p.parents:raise ValueError('unsafe replacement path')
            p.write_bytes(job['code'].encode())
        sandbox=base_sandbox(work,paths)
        if job['language']=='python':
            command=['/usr/bin/python3','-m','pytest','-q','--disable-warnings','--maxfail=3','--junitxml=/work/_cwm_junit.xml']
        elif job['language']=='java':
            sandbox+=['--ro-bind',str(ROOT/'tools/apache-maven-3.9.11'),'/opt/maven','--bind',str(ROOT/'tools/m2'),'/cache/m2',
                '--setenv','JAVA_HOME','/opt/jdk','--setenv','MAVEN_OPTS','-Xmx1536m -XX:ActiveProcessorCount=2']
            command=['/opt/maven/bin/mvn',*maven_args(job['repo']),'-o','-Dmaven.repo.local=/cache/m2','test']
        else:return dict(status='language_recipe_unavailable',pass_tests=False)
        log=logdir/(job['job_id']+'.log');result=run_limited(sandbox+command,work,log)
        xmls=[work/'_cwm_junit.xml'] if job['language']=='python' else list(work.rglob('surefire-reports/TEST-*.xml'))
        counts=xml_counts([p for p in xmls if p.exists()]);result.update(counts=counts,command=command,network_isolated=True,
            pass_tests=result['status']=='ok' and counts['tests']>0 and counts['failures']==0 and counts['errors']==0,
            log=str(log.relative_to(ROOT)))
        return result

def collect_development():
    original={(r['id'],r['key']):r for s in (ROOT/'results/replay_pilot.jsonl').read_text().splitlines() if s and (r:=json.loads(s))}
    refined={(r['id'],r['key']):r for s in (ROOT/'results/refined_replay_pilot.jsonl').read_text().splitlines() if s and (r:=json.loads(s))}
    jobs={}
    for pair,r in original.items():
        if r['language'] not in ('python','java') or not r.get('codes_file'):continue
        codes=json.loads(gzip.decompress((ROOT/r['codes_file']).read_bytes()))
        f=refined.get(pair,{})
        if f.get('code_file'):codes['positive_after_fine']=gzip.decompress((ROOT/f['code_file']).read_bytes()).decode()
        for group,code in codes.items():
            if group=='positive_after':continue # evaluate fine replay; original text agreement separately checked
            commit=r['parent_sha'] if group.endswith('before') else r['sha'];is_negative=group.startswith('negative')
            codehash=hashlib.sha256(code.encode()).hexdigest();identity=(r['repo'],commit,'' if is_negative else r['filename'],'' if is_negative else codehash)
            uid=hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
            j=jobs.setdefault(uid,dict(job_id=uid,repo=r['repo'],commit=commit,language=r['language'],filename=r['filename'],code=None if is_negative else code,code_sha256=codehash,links=[]))
            j['links'].append(dict(id=r['id'],key=r['key'],group=group))
    return sorted(jobs.values(),key=lambda j:(j['language']!='python',j['repo'],j['commit'],j['code'] is not None,j['job_id']))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int);ap.add_argument('--language');a=ap.parse_args()
    (ROOT/'work').mkdir(exist_ok=True);paths=json.loads((ROOT/'records/tool_paths.json').read_text())
    out=ROOT/'results/project_tests_lf.jsonl';done={json.loads(s)['job_id'] for s in out.read_text().splitlines() if s} if out.exists() else set()
    jobs=[j for j in collect_development() if j['job_id'] not in done and (not a.language or j['language']==a.language)]
    if a.limit:jobs=jobs[:a.limit]
    with out.open('a') as f:
        for i,job in enumerate(jobs,1):
            start=time.time()
            try:result=test_job(job,paths)
            except Exception as e:result=dict(status='harness_error',pass_tests=False,error=type(e).__name__+': '+str(e))
            record={k:v for k,v in job.items() if k!='code'}|result;record['total_seconds']=time.time()-start
            f.write(json.dumps(record)+'\n');f.flush()
            print('PROJECT_TEST',i,len(jobs),job['repo'],result['status'],result.get('counts'),round(time.time()-start,1),flush=True)

if __name__=='__main__':main()
