"""Recover stalled public Maven Central transfers, verifying their checksums."""
import concurrent.futures,hashlib,json,re,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];CACHE=ROOT/'tools/m2'
def one(rel):
    url='https://repo.maven.apache.org/maven2/'+rel;dest=CACHE/rel
    with tempfile.TemporaryDirectory(dir=ROOT/'work') as tmp:
        out=Path(tmp)/'artifact';sha=Path(tmp)/'sha1'
        for link,p in ((url,out),(url+'.sha1',sha)):
            subprocess.run(['curl','-sSfL','--connect-timeout','10','--max-time','60','--retry','1','-o',str(p),link],check=True,timeout=130)
        expected=sha.read_text().strip().split()[0];actual=hashlib.sha1(out.read_bytes()).hexdigest();assert expected.lower()==actual
        dest.write_bytes(out.read_bytes());(dest.parent/(dest.name+'.sha1')).write_text(expected)
        marker=dest.parent/'_remote.repositories';line=dest.name+'>central=\n'
        old=marker.read_text() if marker.exists() else ''
        if line not in old:marker.write_text(old+line)
        return dict(path=rel,sha1=actual,bytes=dest.stat().st_size,url=url)
def main():
    names=set()
    for p in CACHE.rglob('*.tmp'):
        m=re.match(r'^(.*?\.(?:jar|pom))\.\d+\.tmp',p.name)
        if m:names.add((p.parent/m[1]).relative_to(CACHE).as_posix())
    records=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        for result in ex.map(one,sorted(names)):records.append(result);print('PREFETCH',result['path'],result['bytes'],flush=True)
    (ROOT/'records/maven_prefetch.json').write_text(json.dumps(records,indent=2))
if __name__=='__main__':main()
