"""Original-first, versioned, offline whole-suite functional validation."""
import argparse,concurrent.futures,datetime,gzip,hashlib,json,os,re,subprocess,sys,tempfile,threading,time,tomllib,urllib.request
from pathlib import Path
from run_project_tests import safe_extract,run_limited,xml_counts
ROOT=Path(__file__).resolve().parents[1]
OLD=Path('/home/icdm/crosslingual-codewatermark/maintenance_upgrade_20261028')
PY311=Path('/home2/icdm/conda_envs/aaai27')
VERSION='v3'
LOCKS={};LOCK_GUARD=threading.Lock()

def sha(data):return hashlib.sha256(data).hexdigest()

def locked(key):
    with LOCK_GUARD:return LOCKS.setdefault(key,threading.Lock())

def selected_rows():
    manifests=json.loads((ROOT/'records/acquisition_summary.json').read_text())
    selected={r['id'] for m in manifests for r in json.loads((ROOT/'records'/('functional_'+m['repo'].replace('/','__')+'.json')).read_text())}
    return [r for p in (ROOT/'data/pairs').glob('*.json.gz') if '.frame.' not in p.name for r in json.loads(gzip.decompress(p.read_bytes())) if r['id'] in selected]

def collect(preflight=False,original_only=False):
    rows=selected_rows()
    if preflight:
        chosen=[]
        for repo in sorted({r['repo'] for r in rows}):
            rr=sorted((r for r in rows if r['repo']==repo),key=lambda r:(r['timestamp'],r['sha']))
            chosen.extend([rr[0],rr[-1]])
        rows=chosen;original_only=True
    scores={}
    if not original_only:
        assert (ROOT/'records/scoring_complete.txt').exists(),'wait for complete scored cohort'
        scores={(r['id'],r['key']):r for line in (ROOT/'results/temporal_scores.jsonl').read_text().splitlines() if line and (r:=json.loads(line))}
    jobs={}
    for row in rows:
        for key in (15485863,32452843,49979687):
            codes={'negative_before':row['before'],'negative_after':row['after']}
            record=scores.get((row['id'],key),{})
            if record.get('codes_file'):codes.update(json.loads(gzip.decompress((ROOT/record['codes_file']).read_bytes())))
            for group,code in codes.items():
                commit=row['parent_sha'] if group.endswith('before') else row['sha']
                identity=(VERSION,row['repo'],commit,row['filename'],sha(code.encode()))
                jid=sha(json.dumps(identity).encode())[:24]
                job=jobs.setdefault(jid,dict(job_id=jid,repo=row['repo'],language=row['language'],commit=commit,filename=row['filename'],code=code,code_sha256=sha(code.encode()),original=group.startswith('negative'),links=[]))
                # An unchanged marked version may share the exact original job.
                job['original']=job['original'] or group.startswith('negative')
                job['links'].append(dict(id=row['id'],key=key,group=group))
    return sorted(jobs.values(),key=lambda j:(not j['original'],j['language']!='python',j['repo'],j['commit'],j['job_id']))

def archive(repo,commit):
    path=ROOT/'data/snapshots'/f"{repo.replace('/','__')}__{commit}.tar.gz"
    path.parent.mkdir(parents=True,exist_ok=True)
    with locked(str(path)):
        if not path.exists():
            tmp=path.with_suffix('.tmp')
            command=['git','-c','core.autocrlf=false','-c','core.eol=lf','--git-dir',str(ROOT/'data/repos'/repo.replace('/','__')),'archive','--format=tar.gz',commit]
            with tmp.open('wb') as f:
                p=subprocess.run(command,stdout=f,stderr=subprocess.PIPE,timeout=120)
            if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
            tmp.replace(path)
    return path

def jdk_for(repo):
    if repo=='checkstyle/checkstyle':return Path(json.loads((ROOT/'records/test_jdk.json').read_text())['home'])
    return Path(json.loads((ROOT/'records/tool_paths.json').read_text())['jdk'])

def pybase(repo):
    if repo=='sphinx-doc/sphinx':return Path((ROOT/'records/python313_path.txt').read_text().strip()).parents[1]
    return PY311

def sandbox(work,repo,envdir=None,network=False):
    args=['bwrap','--ro-bind','/usr','/usr','--ro-bind','/lib','/lib','--ro-bind','/lib64','/lib64','--ro-bind','/etc/alternatives','/etc/alternatives','--ro-bind','/etc/ssl','/etc/ssl','--symlink','usr/bin','/bin','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--bind',str(work),'/work','--chdir','/work','--unshare-all','--die-with-parent','--new-session','--clearenv','--setenv','HOME','/tmp','--setenv','LANG','C.UTF-8','--setenv','LC_ALL','C.UTF-8','--setenv','OPENBLAS_NUM_THREADS','1','--setenv','OMP_NUM_THREADS','1','--setenv','PYTHONHASHSEED','0']
    args+=['--ro-bind',str(ROOT/'tools/sandbox_hosts'),'/etc/hosts']
    if Path('/etc/fonts').exists():args+=['--ro-bind','/etc/fonts','/etc/fonts']
    if network:args+=['--share-net','--ro-bind','/etc/resolv.conf','/etc/resolv.conf']
    if envdir:
        base=pybase(repo)
        args+=['--ro-bind',str(base),str(base),'--bind' if network else '--ro-bind',str(envdir),str(envdir),'--setenv','PATH',str(envdir/'bin')+':/usr/bin:/bin','--setenv','PYTHONPATH','/work/src:/work','--setenv','PYTEST_DISABLE_PLUGIN_AUTOLOAD','1']
        if network:args+=['--ro-bind',str(ROOT/'tools/bootstrap/bin/uv'),'/opt/uv','--bind',str(ROOT/'tools/uv-cache'),'/cache/uv','--setenv','UV_CACHE_DIR','/cache/uv','--setenv','UV_NATIVE_TLS','true']
    else:
        args+=['--ro-bind',str(jdk_for(repo)),'/opt/jdk','--ro-bind',str(OLD/'tools/apache-maven-3.9.11'),'/opt/maven','--bind',str(ROOT/'tools/m2'),'/cache/m2','--setenv','PATH','/opt/jdk/bin:/opt/maven/bin:/usr/bin:/bin','--setenv','JAVA_HOME','/opt/jdk','--setenv','JAVA_TOOL_OPTIONS','-Duser.home=/tmp -XX:ActiveProcessorCount=1 -Xmx1536m','--setenv','MAVEN_OPTS','-Xmx1536m -XX:ActiveProcessorCount=1 -Djava.net.preferIPv4Stack=true']
    return args

def maven(repo):
    cmd=['/opt/maven/bin/mvn','-B','-Dstyle.color=never','-Dmaven.repo.local=/cache/m2','-Dcheckstyle.skip=true','-Dspotless.skip=true','-Denforcer.skip=true','-Dmaven.javadoc.skip=true','-Djacoco.skip=true','-Dpmd.skip=true','-Dspotbugs.skip=true','-Daether.connector.http.requestTimeout=30000','-Daether.connector.http.connectTimeout=10000']
    if repo=='javaparser/javaparser':cmd+=['-pl','javaparser-core-testing','-am']
    return cmd

def historical_dependency(name,job):
    from packaging.version import Version
    folder=ROOT/'records/pypi_metadata';folder.mkdir(exist_ok=True)
    target=folder/(name+'.json')
    with locked(str(target)):
        if target.exists():data=json.loads(target.read_text())
        else:
            req=urllib.request.Request('https://pypi.org/pypi/'+name+'/json',headers={'User-Agent':'research-reproducibility/1.0'})
            with urllib.request.urlopen(req,timeout=60) as response:data=json.load(response)
            target.write_text(json.dumps(data))
    stamp=int(subprocess.check_output(['git','--git-dir',str(ROOT/'data/repos'/job['repo'].replace('/','__')),'show','-s','--format=%ct',job['commit']],text=True).strip())
    versions=[]
    for version,files in data['releases'].items():
        try:v=Version(version)
        except ValueError:continue
        if v.is_prerelease or v.is_devrelease:continue
        eligible=[f for f in files if not f.get('yanked') and datetime.datetime.fromisoformat(f['upload_time_iso_8601'].replace('Z','+00:00')).timestamp()<=stamp]
        if eligible:versions.append(v)
    if not versions:raise ValueError('no historical release: '+name)
    return name+'=='+str(max(versions))

def python_requirements(work,repo,job):
    config=tomllib.loads((work/'pyproject.toml').read_text()) if (work/'pyproject.toml').exists() else {}
    if repo=='Textualize/rich':
        deps=['.','pytest==7.4.4','pytest-cov==3.0.0','attrs==21.4.0','typing_extensions']
        lock=work/'poetry.lock'
        pinned=set()
        if lock.exists():
            for package in tomllib.loads(lock.read_text()).get('package',[]):
                if package['name'] in ('pygments','markdown-it-py','mdurl'):
                    deps.append(package['name']+'=='+package['version'])
                    pinned.add(package['name'])
        for name in ('pygments','markdown-it-py','mdurl'):
            if name not in pinned:deps.append(historical_dependency(name,job))
        return deps
    if repo=='pallets/flask':
        version=config.get('project',{}).get('version','')
        if not version:
            content=(work/'src/flask/__init__.py').read_text()
            found=re.search(r'__version__\s*=\s*[\x22\x27]([^\x22\x27]+)',content)
            version=found.group(1) if found else '3.1'
        numeric=tuple(int(s) for s in re.match(r'(\d+)\.(\d+)',version).groups())
        deps=['.[async,dotenv]','pytest==7.4.4' if numeric<(3,0) else 'pytest==8.4.2']
        deps += [historical_dependency(name,job) for name in ('Werkzeug','click')]
        deps += ['setuptools==65.5.0' if numeric<(3,0) else 'setuptools==75.8.0','wheel']
        return deps
    deps=['.[test]','pytest>=8','pytest-xdist[psutil]','Cython','defusedxml','setuptools','typing_extensions',historical_dependency('Pygments',job)]
    deps += [s for s in config.get('dependency-groups',{}).get('test',[]) if isinstance(s,str)]
    return deps

def prime_java_providers(repo,prepare_log,logdir):
    versions=set(re.findall(r'--- (?:maven-)?surefire(?:-plugin)?:([^: ]+):',prepare_log.read_text(errors='replace')))
    artifacts=[f'org.apache.maven.surefire:{provider}:{version}' for version in sorted(versions) for provider in ('surefire-junit-platform','surefire-junit4','surefire-junit47')]
    engines=ROOT/'tools/m2/org/junit/platform/junit-platform-engine'
    if engines.exists():
        artifacts += ['org.junit.platform:junit-platform-launcher:'+p.name for p in engines.iterdir() if p.is_dir() and p.name[0].isdigit()]
    records=[];folder=ROOT/'records/provider_warmups';folder.mkdir(exist_ok=True)
    for artifact in artifacts:
        uid=sha(artifact.encode())[:24];marker=folder/(uid+'.json')
        with locked(str(marker)):
            if marker.exists():r=json.loads(marker.read_text())
            else:
                with tempfile.TemporaryDirectory(prefix='provider-',dir=ROOT/'work') as td:
                    helper=Path(td)
                    (helper/'pom.xml').write_text('<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>research.environment</groupId><artifactId>provider-cache</artifactId><version>1</version></project>')
                    command=maven('apache/commons-csv')+['org.apache.maven.plugins:maven-dependency-plugin:3.8.1:get','-Dartifact='+artifact,'-Dtransitive=true']
                    r=run_limited(sandbox(helper,repo,network=True)+command,helper,logdir/(uid+'_provider.log'),timeout=300)
                    r['artifact']=artifact;marker.write_text(json.dumps(r,indent=2))
            records.append(r)
    return records

def prepare(work,job):
    repo=job['repo'];identity=repo.replace('/','__')+'__'+job['commit']
    folder=ROOT/'records'/('environments_'+VERSION);folder.mkdir(exist_ok=True)
    marker=folder/(identity+'.json')
    logdir=ROOT/'logs'/('functional_'+VERSION);logdir.mkdir(exist_ok=True)
    envdir=ROOT/'tools'/('envs_'+VERSION)/identity if job['language']=='python' else None
    with locked(str(marker)):
        if marker.exists():return json.loads(marker.read_text()),envdir
        if envdir:
            envdir.parent.mkdir(parents=True,exist_ok=True)
            base=pybase(repo);python=base/'bin'/('python3.13' if repo=='sphinx-doc/sphinx' else 'python')
            p=subprocess.run([str(ROOT/'tools/bootstrap/bin/uv'),'venv','--python',str(python),'--no-project',str(envdir)],capture_output=True,text=True,timeout=60)
            if p.returncode:raise RuntimeError(p.stderr[-1500:])
            deps=python_requirements(work,repo,job)
            command=['/opt/uv','pip','install','--python',str(envdir/'bin/python'),'--index-url','https://pypi.tuna.tsinghua.edu.cn/simple',*deps]
            result=run_limited(sandbox(work,repo,envdir,network=True)+command,work,logdir/(identity+'_prepare.log'),timeout=900)
            result.update(requirements=deps,python=str(python),environment=str(envdir))
            if result['status']=='ok':
                p=subprocess.run([str(ROOT/'tools/bootstrap/bin/uv'),'pip','freeze','--python',str(envdir/'bin/python')],capture_output=True,text=True,timeout=60)
                (folder/(identity+'.freeze.txt')).write_text(p.stdout)
        else:
            command=maven(repo)+['-DskipTests=true','test']
            prepare_log=logdir/(identity+'_prepare.log')
            result=run_limited(sandbox(work,repo,network=True)+command,work,prepare_log,timeout=900)
            result.update(jdk=str(jdk_for(repo)))
            if result['status']=='ok':
                result['provider_warmups']=prime_java_providers(repo,prepare_log,logdir)
                if any(r['status']!='ok' for r in result['provider_warmups']):result['status']='provider_dependency_unavailable'
        result.update(command=command,original_snapshot=True,recipe_version=VERSION)
        marker.write_text(json.dumps(result,indent=2));return result,envdir

def execute(job):
    started=time.time();logdir=ROOT/'logs'/('functional_'+VERSION);logdir.mkdir(exist_ok=True)
    try:
        source=archive(job['repo'],job['commit'])
        with tempfile.TemporaryDirectory(prefix='functional-',dir=ROOT/'work') as td:
            work=Path(td);safe_extract(source,work)
            prep,envdir=prepare(work,job)
            if prep['status']!='ok':
                result=dict(status='original_environment_unavailable',pass_tests=False,preparation=prep)
            else:
                path=work/job['filename']
                if job['original']:assert sha(path.read_bytes())==job['code_sha256'],'original snapshot hash differs'
                path.write_bytes(job['code'].encode())
                if envdir:
                    package={'pallets/flask':'flask','Textualize/rich':'rich','sphinx-doc/sphinx':'sphinx'}[job['repo']]
                    args=['-q','--disable-warnings','--maxfail=3','--junitxml=/work/_cwm_junit.xml','tests']
                    # Full upstream Python suite: optional external builders follow
                    # upstream skip rules. Do not hand-remove failing test modules.
                    code='import '+package+'; assert '+package+'.__file__.startswith("/work/"), '+package+'.__file__; import pytest; raise SystemExit(pytest.main('+repr(args)+'))'
                    command=[str(envdir/'bin/python'),'-c',code]
                else:
                    command=maven(job['repo'])+['-o','test']
                    if job['repo']=='checkstyle/checkstyle':command=['/usr/bin/xvfb-run','-a','-s','-screen 0 1280x1024x24']+command
                result=run_limited(sandbox(work,job['repo'],envdir)+command,work,logdir/(job['job_id']+'.log'),timeout=600)
                xmls=[work/'_cwm_junit.xml'] if envdir else list(work.rglob('surefire-reports/TEST-*.xml'))
                counts=xml_counts([p for p in xmls if p.exists()])
                result.update(counts=counts,command=command,network_isolated=True,suite='full-python-suite' if envdir else 'core-testing-module' if job['repo']=='javaparser/javaparser' else 'full-unit-suite',pass_tests=result['status']=='ok' and counts['tests']>counts['skipped'] and counts['failures']==0 and counts['errors']==0)
    except Exception as e:
        result=dict(status='harness_error',pass_tests=False,error=type(e).__name__+': '+str(e))
    return {k:v for k,v in job.items() if k!='code'}|result|dict(total_seconds=time.time()-started,recipe_version=VERSION)

def main():
    global VERSION
    ap=argparse.ArgumentParser();ap.add_argument('--preflight',action='store_true');ap.add_argument('--original-only',action='store_true');ap.add_argument('--repo');ap.add_argument('--version',default='v3');ap.add_argument('--limit',type=int);a=ap.parse_args();VERSION=a.version
    if not a.preflight and not a.original_only:
        freeze=json.loads((ROOT/'records/functional_recipe_freeze.json').read_text())
        assert freeze['version']==VERSION and freeze['script_sha256']==sha(Path(__file__).read_bytes()),'functional recipe changed'
    jobs=collect(a.preflight,a.original_only)
    (ROOT/'tools/sandbox_hosts').write_text('127.0.0.1 localhost\n::1 localhost\n')
    if a.repo:jobs=[j for j in jobs if j['repo']==a.repo]
    if a.limit:jobs=jobs[:a.limit]
    out=ROOT/'results'/('functional_preflight_'+VERSION+'.jsonl' if a.preflight else 'functional_'+VERSION+'.jsonl')
    done={json.loads(s)['job_id'] for s in out.read_text().splitlines() if s} if out.exists() else set()
    (ROOT/'records'/('functional_jobs_'+('preflight_' if a.preflight else '')+VERSION+'.json')).write_text(json.dumps([{k:v for k,v in j.items() if k!='code'} for j in jobs],indent=2))
    jobs=[j for j in jobs if j['job_id'] not in done]
    with out.open('a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        futures={ex.submit(execute,j):j for j in jobs}
        for i,future in enumerate(concurrent.futures.as_completed(futures),1):
            r=future.result();f.write(json.dumps(r)+'\n');f.flush()
            print('FUNCTIONAL',i,len(jobs),r['repo'],r['status'],r.get('counts'),round(r['total_seconds'],1),flush=True)
    print('FUNCTIONAL_COMPLETE',len(jobs),VERSION,flush=True)
    if not a.repo and not a.limit:
        kind='preflight' if a.preflight else 'originals' if a.original_only else 'functional'
        (ROOT/'records'/f'{kind}_complete_{VERSION}.txt').write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())

if __name__=='__main__':main()
