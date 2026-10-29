"""Download official public validation/test files and retain checksums."""
import hashlib,json,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
dest=ROOT/'data'/'codecontests';dest.mkdir(parents=True,exist_ok=True)
base='https://huggingface.co/datasets/deepmind/code_contests/resolve/main/'
files=['README.md','data/valid-00000-of-00001-5e672c5751f060d3.parquet','data/test-00000-of-00001-9c49eeff30aacaa8.parquet']
manifest=[]
for rel in files:
    p=dest/Path(rel).name
    if not p.exists():
        req=urllib.request.Request(base+rel,headers={'User-Agent':'research-reproduction/1.0'})
        with urllib.request.urlopen(req,timeout=120) as response,p.with_suffix(p.suffix+'.part').open('wb') as f:
            while chunk:=response.read(1024*1024):f.write(chunk)
        p.with_suffix(p.suffix+'.part').replace(p)
    manifest.append({'url':base+rel,'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    print(p.name,p.stat().st_size,flush=True)
(dest/'manifest.json').write_text(json.dumps(manifest,indent=2))
