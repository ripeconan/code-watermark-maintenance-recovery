import hashlib,json,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'tools';root.mkdir(exist_ok=True)
def getjson(url):
    req=urllib.request.Request(url,headers={'User-Agent':'code-watermark-research'})
    with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)
def download(url,name,expected):
    p=root/name
    if not p.exists():
        with urllib.request.urlopen(url,timeout=120) as r,p.with_suffix(p.suffix+'.part').open('wb') as f:
            while b:=r.read(1024*1024):f.write(b)
        p.with_suffix(p.suffix+'.part').replace(p)
    sha=hashlib.sha256(p.read_bytes()).hexdigest();assert sha==expected,(name,sha,expected)
    print(name,p.stat().st_size,flush=True)
    return dict(url=url,file=name,sha256=sha,bytes=p.stat().st_size)
records=[]
release=getjson('https://api.github.com/repos/adoptium/temurin17-binaries/releases/latest')
package=next(x for x in release['assets'] if x['name'].startswith('OpenJDK17U-jdk_x64_linux_hotspot_') and x['name'].endswith('.tar.gz'))
checksum_asset=next(x for x in release['assets'] if x['name']==package['name']+'.sha256.txt')
with urllib.request.urlopen(checksum_asset['browser_download_url'],timeout=90) as r:checksum=r.read().decode().split()[0]
records.append(download(package['browser_download_url'],package['name'],checksum))
meta=getjson('https://pypi.org/pypi/clang-format/20.1.8/json')
wheel=next(x for x in meta['urls'] if 'manylinux' in x['filename'] and 'x86_64' in x['filename'])
records.append(download(wheel['url'],wheel['filename'],wheel['digests']['sha256']))
(root/'manifest.json').write_text(json.dumps(records,indent=2))
