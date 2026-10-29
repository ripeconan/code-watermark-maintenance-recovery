"""Acquire pinned public git history and outcome-independent maintenance pairs.

Local metadata/data acquisition only. No repository code is executed.
"""
import argparse, collections, gzip, hashlib, json, os, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = [
    ('python','development','mahmoud/boltons'),
    ('python','calibration','pallets/itsdangerous'),
    ('python','test','pallets/click'),
    ('java','development','google/gson'),
    ('java','calibration','jhy/jsoup'),
    ('java','test','junit-team/junit4'),
    ('cpp','development','fmtlib/fmt'),
    ('cpp','calibration','gabime/spdlog'),
    ('cpp','test','nlohmann/json'),
]
EXCLUDE = set('test tests testing benchmark benchmarks example examples doc docs vendor third_party third-party generated build single_include singleinclude'.split())
EXTENSIONS = {'python':{'.py'}, 'java':{'.java'}, 'cpp':{'.cpp','.cc','.cxx','.h','.hpp'}}

def git(repo,*args,timeout=90):
    p=subprocess.run(['git','-c','core.quotepath=false','--git-dir',str(repo),*args],capture_output=True,timeout=timeout)
    if p.returncode: raise RuntimeError(p.stderr.decode('utf8','replace')[-1500:])
    return p.stdout

def acquire(language, split, name):
    dest=ROOT/'data/repos'/name.replace('/','__');dest.parent.mkdir(parents=True,exist_ok=True)
    manifest_path=ROOT/'records'/f"acquire_{name.replace('/','__')}.json"
    if manifest_path.exists():
        old=json.loads(manifest_path.read_text(encoding='utf8'))
        if old.get('complete'): return old
    started=time.time()
    if not (dest/'HEAD').exists():
        p=subprocess.run(['git','-c','credential.interactive=never','-c','http.sslBackend=openssl','clone','--bare','--depth','400','--single-branch',f'https://github.com/{name}.git',str(dest)],capture_output=True,timeout=600,env={**os.environ,'GIT_TERMINAL_PROMPT':'0'})
        if p.returncode:raise RuntimeError(p.stderr.decode('utf8','replace')[-2000:])
    pin=git(dest,'rev-list','-1','--before=2026-10-27T23:59:59Z','HEAD').decode().strip()
    if not pin:raise ValueError('No commit before cutoff in downloaded history')
    license_paths=[s for s in git(dest,'ls-tree','--name-only',pin).decode().splitlines() if s.lower().startswith(('license','copying'))]
    if not license_paths: raise ValueError('No root license to inspect')
    licenses=[]
    for lp in license_paths:
        raw=git(dest,'show',f'{pin}:{lp}'); out=ROOT/'data/licenses'/f"{name.replace('/','__')}__{Path(lp).name}"
        out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(raw)
        licenses.append(dict(path=lp,sha256=hashlib.sha256(raw).hexdigest(),local=str(out.relative_to(ROOT))))
    lines=git(dest,'log','--no-merges','--max-count=250','--format=%H %P',pin).decode().splitlines()
    counts=collections.Counter();pairs=[];census=[]
    for line in lines:
        ids=line.split()
        if len(ids)!=2:
            counts['no_single_available_parent']+=1;continue
        sha,parent=ids
        try:diff=git(dest,'diff-tree','--no-commit-id','--name-status','-r','--no-renames',parent,sha).decode('utf8').splitlines()
        except RuntimeError as e:
            counts['parent_unavailable']+=1;continue
        for item in diff:
            fields=item.split('\t');status,path=fields[0],fields[-1];p=Path(path)
            if p.suffix.lower() not in EXTENSIONS[language]:continue
            record=dict(repo=name,language=language,split=split,sha=sha,parent_sha=parent,filename=path,status=status)
            reason=None
            if any(part.lower() in EXCLUDE for part in p.parts):reason='excluded_path'
            elif language=='python' and (p.name.startswith('test_') or p.name.endswith('_test.py')):reason='test_filename'
            elif status!='M':reason='not_modified_existing_file'
            else:
                try:
                    before=git(dest,'show',f'{parent}:{path}');after=git(dest,'show',f'{sha}:{path}')
                    if max(len(before),len(after))>80000:reason='over_80000_bytes'
                    elif b'\0' in before or b'\0' in after:reason='binary'
                    elif before==after:reason='identical'
                    else:
                        before_text=before.decode('utf8');after_text=after.decode('utf8')
                except UnicodeDecodeError:reason='non_utf8'
                except RuntimeError:reason='blob_unavailable'
            counts[reason or 'eligible']+=1
            census.append({**record,'exclusion':reason})
            if reason:continue
            uid=hashlib.sha256(('maintenance-upgrade-v1|'+name+'|'+sha+'|'+path).encode()).hexdigest()
            pairs.append({**record,'id':uid,'before':before_text,'after':after_text,
                'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(after).hexdigest(),
                'html_url':f'https://github.com/{name}/commit/{sha}'})
    pairs=sorted(pairs,key=lambda r:r['id'])[:80]
    data_dir=ROOT/'data/pairs';data_dir.mkdir(parents=True,exist_ok=True)
    output=data_dir/f"{name.replace('/','__')}.json.gz"
    raw=json.dumps(pairs,ensure_ascii=False).encode();output.write_bytes(gzip.compress(raw,mtime=0))
    census_path=ROOT/'data'/f"census_{name.replace('/','__')}.json.gz"
    census_path.write_bytes(gzip.compress(json.dumps(census).encode(),mtime=0))
    manifest=dict(repo=name,language=language,split=split,pin=pin,license=licenses,commits_examined=len(lines),
        counts=dict(counts),sampled=len(pairs),unique_sample_commits=len({r['sha'] for r in pairs}),
        data_path=str(output.relative_to(ROOT)),sha256_uncompressed=hashlib.sha256(raw).hexdigest(),
        acquired_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),seconds=time.time()-started,complete=True)
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('ACQUIRED',name,'eligible',counts['eligible'],'sampled',len(pairs),'seconds',round(time.time()-started,1),flush=True)
    return manifest

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo');a=ap.parse_args()
    (ROOT/'records').mkdir(parents=True,exist_ok=True);manifests=[]
    for args in PROJECTS:
        if a.repo and args[2]!=a.repo:continue
        try:manifests.append(acquire(*args))
        except Exception as e:
            error=dict(repo=args[2],error=type(e).__name__+': '+str(e));manifests.append(error)
            print('ACQUISITION_ERROR',json.dumps(error),flush=True)
    aggregate='acquisition.json' if not a.repo else 'acquisition_retry_'+a.repo.replace('/','__')+'.json'
    (ROOT/'records'/aggregate).write_text(json.dumps(manifests,indent=2),encoding='utf8')

if __name__=='__main__':main()
