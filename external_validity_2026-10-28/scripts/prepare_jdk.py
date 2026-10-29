"""Fetch and verify a public Temurin 21 runtime for Checkstyle's declared build."""
import hashlib,json,tarfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    manifest=ROOT/'records/test_jdk.json'
    if manifest.exists():
        old=json.loads(manifest.read_text())
        if Path(old['home']).is_dir():print('JDK_AVAILABLE',old['home']);return
    api='https://api.adoptium.net/v3/assets/latest/21/hotspot?architecture=x64&heap_size=normal&image_type=jdk&jvm_impl=hotspot&os=linux&vendor=eclipse'
    cached=ROOT/'records/jdk_download_metadata.json'
    if cached.exists():release=json.loads(cached.read_text())
    else:
        with urllib.request.urlopen(urllib.request.Request(api,headers={'User-Agent':'Mozilla/5.0 research-environment-setup'}),timeout=60) as r:data=json.load(r)
        release=data[0]
    package=release['binary']['package']
    (ROOT/'records/jdk_download_metadata.json').write_text(json.dumps(release,indent=2))
    dest=ROOT/'tools'/package['name']
    if not dest.exists() or hashlib.sha256(dest.read_bytes()).hexdigest()!=package['checksum']:
        print('DOWNLOAD',package['name'],flush=True)
        with urllib.request.urlopen(urllib.request.Request(package['link'],headers={'User-Agent':'Mozilla/5.0 research-environment-setup'}),timeout=120) as r,dest.open('wb') as f:
            while block:=r.read(1024*1024):f.write(block)
    assert hashlib.sha256(dest.read_bytes()).hexdigest()==package['checksum']
    with tarfile.open(dest) as archive:
        top=archive.getnames()[0].split('/')[0];archive.extractall(ROOT/'tools',filter='data')
    result=dict(home=str(ROOT/'tools'/top),sha256=package['checksum'],source=package['link'],api=api,version=release['version'])
    manifest.write_text(json.dumps(result,indent=2));print('JDK_READY',result['home'],flush=True)
if __name__=='__main__':main()
