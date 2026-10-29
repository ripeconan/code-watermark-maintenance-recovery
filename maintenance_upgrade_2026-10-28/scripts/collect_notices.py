"""Preserve root upstream NOTICE files beside already collected licenses."""
import json,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
out=[]
for meta in list((ROOT/'records').glob('acquire_*.json'))+list((ROOT/'records').glob('new_project_*.json')):
    r=json.loads(meta.read_text(encoding='utf-8'));repo=r.get('repo');pin=r.get('pin')
    if not repo or not pin:continue
    gitdir=ROOT/'data/repos'/repo.replace('/','__')
    if not gitdir.exists():continue
    names=subprocess.check_output(['git','--git-dir',str(gitdir),'ls-tree','--name-only',pin],text=True).splitlines()
    for name in names:
        if name.upper().startswith('NOTICE'):
            code=subprocess.check_output(['git','--git-dir',str(gitdir),'show',pin+':'+name])
            dest=ROOT/'data/licenses'/(repo.replace('/','__')+'__'+name);dest.write_bytes(code)
            out.append(dict(repo=repo,pin=pin,path=name,local=dest.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(code).hexdigest()))
(ROOT/'records/notice_files.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
