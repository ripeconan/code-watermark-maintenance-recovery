"""New fixed-frame project-local calibration cohort; run acquisition on inner."""
import collections,gzip,hashlib,json,os,random,subprocess,time
from pathlib import Path
from acquire_repositories import git,EXCLUDE,EXTENSIONS
ROOT=Path(__file__).resolve().parents[1]
PROJECTS=[('python','sympy/sympy'),('python','networkx/networkx'),('java','apache/commons-lang'),('java','apache/commons-collections')]

def h(s):return hashlib.sha256(s.encode()).hexdigest()

def acquire(lang,name):
    base=ROOT/'data/project_calibration';base.mkdir(exist_ok=True)
    stem=name.replace('/','__');record=ROOT/'records'/f'new_project_{stem}.json'
    frame_file=base/(stem+'.frame.json.gz')
    if record.exists() and json.loads(record.read_text()).get('complete') and frame_file.exists():return
    repo=ROOT/'data/repos'/stem;repo.parent.mkdir(exist_ok=True);start=time.time()
    if not (repo/'HEAD').exists():
        p=subprocess.run(['git','clone','--bare','--depth','1200','--single-branch',f'https://github.com/{name}.git',str(repo)],capture_output=True,timeout=1800,env={**os.environ,'GIT_TERMINAL_PROMPT':'0'})
        if p.returncode:raise RuntimeError(p.stderr.decode('utf8','replace')[-2000:])
    valid=subprocess.run(['git','--git-dir',str(repo),'rev-parse','--verify','HEAD'],capture_output=True)
    if valid.returncode:
        # Resume an interrupted transport without changing the sampling depth.
        p=subprocess.run(['git','--git-dir',str(repo),'fetch','--depth','1200',f'https://github.com/{name}.git','HEAD'],capture_output=True,timeout=1800)
        if p.returncode:raise RuntimeError(p.stderr.decode('utf8','replace')[-2000:])
        git(repo,'update-ref',git(repo,'symbolic-ref','HEAD').decode().strip(),'FETCH_HEAD')
    pin=git(repo,'rev-list','-1','--before=2026-10-27T23:59:59Z','HEAD').decode().strip()
    licenses=[p for p in git(repo,'ls-tree','--name-only',pin).decode().splitlines() if p.lower().startswith(('license','copying'))]
    if not licenses:raise ValueError('Missing public source license')
    for p in licenses:
        raw=git(repo,'show',f'{pin}:{p}');(ROOT/'data/licenses'/f'{stem}__{Path(p).name}').write_bytes(raw)
    commits=git(repo,'log','--no-merges','--max-count=600','--format=%H %P',pin).decode().splitlines()
    nominations=collections.defaultdict(list);counts=collections.Counter()
    for line in commits:
        ids=line.split()
        if len(ids)!=2:counts['missing_parent']+=1;continue
        sha,parent=ids
        try:changes=git(repo,'diff-tree','--no-commit-id','--name-status','-r','--no-renames',parent,sha).decode().splitlines()
        except RuntimeError:counts['unavailable_parent']+=1;continue
        for change in changes:
            st,path=change.split('\t',1);p=Path(path)
            if p.suffix.lower() not in EXTENSIONS[lang]:continue
            if any(part.lower() in EXCLUDE for part in p.parts) or (lang=='python' and (p.name.startswith('test_') or p.name.endswith('_test.py'))):counts['excluded_path']+=1;continue
            if st!='M':counts['not_modified_existing_file']+=1;continue
            nominations[path].append((h(f'local-frame-choice|{name}|{sha}|{path}'),sha,parent))
    frame=[]
    for path,choices in sorted(nominations.items()):
        for _,sha,parent in sorted(choices):
            try:
                before=git(repo,'show',f'{parent}:{path}');after=git(repo,'show',f'{sha}:{path}')
                if max(len(before),len(after))>80000:counts['over_80000_bytes']+=1;continue
                if b'\0' in before or b'\0' in after:counts['binary']+=1;continue
                if before==after:counts['identical']+=1;continue
                x,y=before.decode('utf8'),after.decode('utf8')
            except (RuntimeError,UnicodeDecodeError):counts['unavailable_or_nonutf8']+=1;continue
            frame.append(dict(id=h(f'local-calibration-v2|{name}|{sha}|{path}'),repo=name,language=lang,sha=sha,parent_sha=parent,filename=path,
                before=x,after=y,before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=hashlib.sha256(after).hexdigest(),
                html_url=f'https://github.com/{name}/commit/{sha}'))
            break
    seen=set();unique=[]
    for r in sorted(frame,key=lambda r:h('deduplicate|'+r['id'])):
        hashes={r['before_sha256'],r['after_sha256']}
        if seen&hashes:counts['duplicate_program_snapshot']+=1;continue
        unique.append(r);seen|=hashes
    # Frame fixed before random sampling/splitting; no outcomes affect it.
    unique.sort(key=lambda r:r['filename'])
    frame_file.write_bytes(gzip.compress(json.dumps(unique).encode(),mtime=0))
    random.Random(2026102805).shuffle(unique)
    selected=unique[:160];ncal=len(selected)//2
    for i,r in enumerate(selected):r['split']='calibration' if i<ncal else 'test';r['cohort']='project_local_v2'
    tests=sorted([r for r in selected if r['split']=='test'],key=lambda r:h('functional-subsample|'+r['id']))[:8]
    raw=json.dumps(selected).encode();dest=base/(stem+'.json.gz')
    if dest.exists():assert gzip.decompress(dest.read_bytes())==raw,'frozen selection changed'
    else:dest.write_bytes(gzip.compress(raw,mtime=0))
    selection=[{k:r[k] for k in ('id','repo','language','sha','parent_sha','filename')} for r in tests]
    (ROOT/'records'/f'new_functional_{stem}.json').write_text(json.dumps(selection,indent=2))
    metadata=dict(repo=name,language=lang,pin=pin,licenses=licenses,commits_examined=len(commits),nominated_paths=len(nominations),
        eligible_paths=len(frame),unique_frame=len(unique),sampled=len(selected),calibration=ncal,test=len(selected)-ncal,
        exclusions=dict(counts),sha256_uncompressed=hashlib.sha256(raw).hexdigest(),complete=True,seconds=time.time()-start)
    record.write_text(json.dumps(metadata,indent=2));print('NEW_PROJECT',json.dumps(metadata),flush=True)
    # Archive only the prospectively selected functional subsample, all on Linux.
    snapshots=ROOT/'data/project_snapshots_lf';snapshots.mkdir(exist_ok=True)
    for sha in sorted({r[k] for r in tests for k in ('sha','parent_sha')}):
        out=snapshots/f'{stem}__{sha}.tar.gz'
        if not out.exists():subprocess.run(['git','-c','core.autocrlf=false','-c','core.eol=lf','--git-dir',str(repo),'archive','--format=tar.gz','-o',str(out),sha],check=True,timeout=120)

def main():
    for lang,name in PROJECTS:
        try:acquire(lang,name)
        except Exception as e:
            p=ROOT/'records'/('new_project_error_'+name.replace('/','__')+'.json');p.write_text(json.dumps(dict(repo=name,error=type(e).__name__+': '+str(e)),indent=2))
            print('NEW_PROJECT_ERROR',name,str(e),flush=True)

if __name__=='__main__':main()
