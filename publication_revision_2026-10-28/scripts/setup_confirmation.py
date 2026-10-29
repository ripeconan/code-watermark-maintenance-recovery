import hashlib,json,subprocess,tarfile,time,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
data=ROOT/'data/codecontests'
for r in ([] if (ROOT/'data/confirmation_tasks.json').exists() else json.loads((data/'manifest.json').read_text())):
    p=data/r['file']
    good=p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
    if not good:
        if p.exists():p.rename(p.with_name(p.name+'.incomplete.'+str(int(time.time()))))
        with urllib.request.urlopen(r['url'],timeout=120) as response,p.open('wb') as f:
            while chunk:=response.read(1024*1024):f.write(chunk)
        assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],p
    print('DATA_VERIFIED',p.name,flush=True)
toolroot=ROOT/'tools'
for r in json.loads((toolroot/'manifest.json').read_text()):
    p=toolroot/r['file'];assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
    if p.name.endswith('.tar.gz'):
        with tarfile.open(p) as archive:
            for member in archive.getmembers():
                target=(toolroot/member.name).resolve();assert target.is_relative_to(toolroot.resolve())
            top=archive.getnames()[0].split('/')[0]
            if not (toolroot/top/'bin/javac').exists():archive.extractall(toolroot)
        jdk=toolroot/top
    else:
        dest=toolroot/'clang'
        if not dest.exists():
            dest.mkdir()
            with zipfile.ZipFile(p) as archive:archive.extractall(dest)
        binary=next(dest.glob('clang_format/data/bin/clang-format'));binary.chmod(0o755)
paths={'jdk':str(jdk),'java':str(jdk/'bin/java'),'clang':str(binary),'jar':'/home2/icdm/tools/google-java-format-1.17.0-all-deps.jar',
       'vendor':'/home2/icdm/crosslingual-codewatermark/upgrade_probe_20261019/vendor/SEW-3c873186a56033e73347391b7aedebce1f7f71d0'}
(ROOT/'records/tool_paths.json').write_text(json.dumps(paths,indent=2))
for cmd in ([str(jdk/'bin/java'),'-version'],[str(jdk/'bin/javac'),'-version'],[str(binary),'--version']):
    p=subprocess.run(cmd,capture_output=True,text=True);print(p.stdout,p.stderr,flush=True);assert p.returncode==0
print('SETUP_DONE',flush=True)
