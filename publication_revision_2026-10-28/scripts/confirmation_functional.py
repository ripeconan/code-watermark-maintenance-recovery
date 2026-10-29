"""Run paired public CodeContests programs in bwrap; no network/host home access."""
import argparse,concurrent.futures,hashlib,json,math,os,re,resource,signal,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def sha(s):return hashlib.sha256(s.encode()).hexdigest()


def normalize(s):return s.split()


def matches(a,b):
    aa=normalize(a);bb=normalize(b)
    if len(aa)!=len(bb):return False
    for x,y in zip(aa,bb):
        if x==y:continue
        try:
            xf,yf=float(x),float(y)
            if not math.isfinite(xf) or not math.isfinite(yf) or not math.isclose(xf,yf,rel_tol=1e-6,abs_tol=1e-6):return False
        except ValueError:return False
    return True


def init(jdk):
    global JDK
    JDK=jdk


def sandbox(td,cmd,input_text='',compile_step=False,java=False):
    prefix=['bwrap','--ro-bind','/usr','/usr','--ro-bind','/lib','/lib','--ro-bind','/lib64','/lib64',
            '--ro-bind','/etc/alternatives','/etc/alternatives',
            '--symlink','usr/bin','/bin','--proc','/proc','--dev','/dev','--tmpfs','/tmp',
            '--bind',str(td),'/work','--ro-bind',JDK,'/opt/jdk','--chdir','/work',
            '--unshare-all','--die-with-parent','--new-session','--clearenv','--setenv','PATH','/usr/bin:/bin:/opt/jdk/bin',
            '--setenv','LANG','C.UTF-8','--setenv','LC_ALL','C.UTF-8','--setenv','PYTHONHASHSEED','0']
    def limits():
        resource.setrlimit(resource.RLIMIT_CPU,((25,26) if compile_step else (8,9)))
        resource.setrlimit(resource.RLIMIT_FSIZE,(8*1024*1024,8*1024*1024))
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        if not java:resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    out=Path(td)/'.harness_stdout';err=Path(td)/'.harness_stderr'
    with out.open('wb') as fo,err.open('wb') as fe:
        p=subprocess.Popen(prefix+cmd,stdin=subprocess.PIPE,stdout=fo,stderr=fe,start_new_session=True,preexec_fn=limits)
        try:
            p.communicate(input_text.encode(),timeout=35 if compile_step else 12);status='ok' if p.returncode==0 else 'runtime_error'
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);p.wait();status='timeout'
    output=out.read_bytes()[:2*1024*1024].decode('utf8','replace');error=err.read_bytes()[-1500:].decode('utf8','replace')
    return dict(status=status,returncode=p.returncode,output=output,error=error)


def execute(task,code):
    lang=task['language'];result={'sha256':sha(code),'language':lang,'compile_ok':False,'cases':[]}
    with tempfile.TemporaryDirectory(prefix='cwm-confirm-') as td:
        root=Path(td)
        if lang=='python':
            (root/'program.py').write_text(code);compile_cmd=['/usr/bin/python3','-m','py_compile','program.py'];run=['/usr/bin/python3','-I','program.py']
        elif lang=='cpp':
            (root/'program.cpp').write_text(code);compile_cmd=['/usr/bin/g++','-std=c++17','-O0','-w','program.cpp','-o','program'];run=['/work/program']
        else:
            package=re.search(r'^\s*package\s+([\w.]+)\s*;',code,re.M)
            cls=re.search(r'\bpublic\s+(?:(?:final|abstract)\s+)?class\s+(\w+)',code)
            if cls is None:cls=re.search(r'\bclass\s+(\w+)',code)
            if cls is None:return {**result,'error':'no Java class'}
            name=cls.group(1);(root/(name+'.java')).write_text(code)
            main=(package.group(1)+'.' if package else '')+name
            compile_cmd=['/opt/jdk/bin/javac','-J-Xmx512m','-encoding','UTF-8','-d','.',name+'.java']
            run=['/opt/jdk/bin/java','-Xmx256m','-Xss16m','-XX:ActiveProcessorCount=1','-cp','.',main]
        comp=sandbox(td,compile_cmd,compile_step=True,java=lang=='java')
        result['compile_ok']=comp['status']=='ok';result['compile_error']=comp['error']
        if not result['compile_ok']:return result
        inf=task.get('input_file') or '';outf=task.get('output_file') or ''
        if any(x and (Path(x).name!=x or x.startswith('.')) for x in (inf,outf)):
            return {**result,'error':'unsupported file IO path'}
        for t in task['tests']:
            if inf:(root/inf).write_text(t['input'])
            if outf and (root/outf).exists():(root/outf).unlink()
            r=sandbox(td,run,input_text=t['input'],java=lang=='java')
            if outf:
                if (root/outf).exists():r['output']=(root/outf).read_text(errors='replace')[:2*1024*1024]
                else:r['status']='missing_output_file'
            result['cases'].append(dict(kind=t['kind'],index=t['index'],status=r['status'],returncode=r['returncode'],
                expected_match=r['status']=='ok' and matches(r['output'],t['output']),output=r['output'],error=r['error']))
            if r['status']=='timeout':break
        result['completed']=len(result['cases'])==len(task['tests']) and all(r['status']=='ok' for r in result['cases'])
        result['benchmark_pass']=result['completed'] and all(r['expected_match'] for r in result['cases'])
    return result


def work(job):
    task,codes=job;start=time.time();reference=execute(task,task['code']);records=[reference]
    cache={reference['sha256']:reference}
    for h,code in codes.items():
        if h in cache:continue
        r=execute(task,code);cache[h]=r;records.append(r)
    for r in records:
        r['behavior_preserved']=bool(reference.get('completed') and r.get('completed') and
            all(matches(a['output'],b['output']) for a,b in zip(reference['cases'],r['cases'])))
        r['source_benchmark_pass']=bool(reference.get('benchmark_pass'))
    for r in records:
        for case in r['cases']:
            case['output_sha256']=sha(case.pop('output'))
    return dict(id=task['id'],language=task['language'],split=task['split'],results=records,seconds=time.time()-start)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--jdk',required=True)
    ap.add_argument('--out',required=True);ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
    tasks={(t['id'],t['language']):t for t in json.loads((ROOT/'data/confirmation_tasks.json').read_text())}
    codes={}
    for line in Path(a.input).read_text().split('\n'):
        if not line:continue
        r=json.loads(line);key=(r['id'],r['language']);target=codes.setdefault(key,{})
        for group in r['groups'].values():
            for variant in group['variants'].values():target[variant['sha256']]=variant['code']
    out=Path(a.out);done=set()
    if out.exists():
        for line in out.read_text().split('\n'):
            if line:
                r=json.loads(line);done.add((r['id'],r['language']))
    jobs=[(tasks[k],c) for k,c in codes.items() if k not in done]
    print('READY',len(jobs),'tasks',sum(len(c) for _,c in jobs),'distinct task/code pairs',flush=True);start=time.time()
    with out.open('a') as f,concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,initializer=init,initargs=(a.jdk,)) as ex:
        for i,r in enumerate(ex.map(work,jobs,chunksize=1),1):
            f.write(json.dumps(r)+'\n');f.flush();print('TASK',i,len(jobs),r['language'],r['id'],round(r['seconds'],1),flush=True)
    print('DONE',len(jobs),round(time.time()-start,1),flush=True)


if __name__=='__main__':main()
