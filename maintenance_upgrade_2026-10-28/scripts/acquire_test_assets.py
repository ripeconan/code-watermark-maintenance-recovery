"""Acquire exact public project snapshots and ordinary test dependencies locally."""
import argparse,gzip,hashlib,json,subprocess,tarfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--selection',default='records/replay_pilot_selection.json');a=ap.parse_args()
    selected={r['id'] for r in json.loads((ROOT/a.selection).read_text())};pairs=[]
    for p in (ROOT/'data/pairs').glob('*.gz'):pairs.extend(r for r in json.loads(gzip.decompress(p.read_bytes())) if r['id'] in selected)
    snapshots=ROOT/'data/project_snapshots_lf';snapshots.mkdir(exist_ok=True)
    manifest=[]
    for repo,sha in sorted({(r['repo'],r[k]) for r in pairs for k in ('sha','parent_sha')}):
        dst=snapshots/f"{repo.replace('/','__')}__{sha}.tar.gz"
        if not dst.exists():
            subprocess.run(['git','-c','core.autocrlf=false','-c','core.eol=lf','--git-dir',str(ROOT/'data/repos'/repo.replace('/','__')),'archive','--format=tar.gz','-o',str(dst),sha],check=True,timeout=120)
        # Every sampled source file in the archived commit must equal its git
        # blob byte-for-byte. Windows autocrlf must not change research fixtures.
        checked=[]
        with tarfile.open(dst) as tf:
            for pair in pairs:
                if pair['repo']!=repo or sha not in (pair['sha'],pair['parent_sha']):continue
                name=pair['filename'];actual=tf.extractfile(name).read()
                expected=pair['before_sha256'] if sha==pair['parent_sha'] else pair['after_sha256']
                assert hashlib.sha256(actual).hexdigest()==expected,(repo,sha,name,'archive/blob mismatch')
                checked.append(name)
        manifest.append(dict(repo=repo,sha=sha,path=str(dst.relative_to(ROOT)),sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))
    (ROOT/'records/project_snapshots_lf.json').write_text(json.dumps(manifest,indent=2))
    print('PROJECT_SNAPSHOTS',len(manifest),sum((ROOT/r['path']).stat().st_size for r in manifest),flush=True)
    tools=ROOT/'tools';tools.mkdir(exist_ok=True);wheels=tools/'pytest_wheels';wheels.mkdir(exist_ok=True)
    subprocess.run(['python','-m','pip','download','--dest',str(wheels),'pytest==8.4.2','exceptiongroup==1.3.0','tomli==2.2.1'],check=True,timeout=240)
    packages=tools/'test_packages';packages.mkdir(exist_ok=True)
    subprocess.run(['python','-m','pip','install','--no-index','--find-links',str(wheels),'--target',str(packages),'--no-compile','pytest==8.4.2','exceptiongroup==1.3.0','tomli==2.2.1'],check=True,timeout=120)
    maven=tools/'apache-maven-3.9.11-bin.tar.gz'
    if not maven.exists():
        url='https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.11/apache-maven-3.9.11-bin.tar.gz'
        with urllib.request.urlopen(url,timeout=60) as response:maven.write_bytes(response.read())
        with urllib.request.urlopen(url+'.sha512',timeout=30) as response:expected=response.read().decode().strip().split()[0]
        assert hashlib.sha512(maven.read_bytes()).hexdigest()==expected
        (ROOT/'records/maven_source.json').write_text(json.dumps(dict(url=url,sha512=expected),indent=2))
    bundle=ROOT/'records/test_assets_lf.tar.gz'
    with tarfile.open(bundle,'w:gz') as tf:
        for p in list(snapshots.glob('*.gz'))+list(packages.rglob('*'))+[maven,ROOT/'records/project_snapshots_lf.json',ROOT/'records/maven_source.json']:
            if p.is_file():tf.add(p,arcname=str(p.relative_to(ROOT)))
    print('TEST_ASSETS_BUNDLE',bundle.stat().st_size,flush=True)

if __name__=='__main__':main()
