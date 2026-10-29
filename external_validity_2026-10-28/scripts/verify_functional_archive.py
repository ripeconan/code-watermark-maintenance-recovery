"""Verify the transferred archive and every extracted evidence file."""
import argparse,collections,datetime,hashlib,json,zipfile
from pathlib import Path

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--metadata',type=Path,required=True);ap.add_argument('--destination',type=Path,required=True);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
    expected=json.loads(a.metadata.read_text(encoding='utf-8'))
    archive_hash=digest(a.archive)
    assert archive_hash==expected['sha256'] and a.archive.stat().st_size==expected['bytes']
    dest=a.destination.resolve();assert not dest.exists(),'preserve any existing extracted evidence'
    with zipfile.ZipFile(a.archive) as z:
        raw=z.read('FUNCTIONAL_EVIDENCE_MANIFEST.json');manifest=json.loads(raw)
        entries=manifest['files'];names=[r['path'] for r in entries]
        assert len(names)==len(set(names))==expected['files']
        assert len(z.namelist())==len(names)+1 and set(z.namelist())==set(names)|{'FUNCTIONAL_EVIDENCE_MANIFEST.json'}
        groups=collections.Counter(name.casefold() for name in names)
        aliases={}
        for name in names:
            if groups[name.casefold()]>1:
                p=Path(name)
                suffix='__case_'+hashlib.sha256(name.encode()).hexdigest()[:10]
                aliases[name]=str(p.with_name(p.stem+suffix+p.suffix)).replace('\\','/')
        mapped=[aliases.get(name,name) for name in names]
        assert len({name.casefold() for name in mapped})==len(names)
        targets=[]
        for r in entries:
            path=(dest/aliases.get(r['path'],r['path'])).resolve()
            assert dest in path.parents and ':' not in r['path'],'unsafe member path'
            targets.append(path)
        dest.mkdir(parents=True)
        for r,path in zip(entries,targets):
            path.parent.mkdir(parents=True,exist_ok=True)
            h=hashlib.sha256();size=0
            with z.open(r['path']) as src,path.open('xb') as out:
                for chunk in iter(lambda:src.read(1024*1024),b''):
                    h.update(chunk);size+=len(chunk);out.write(chunk)
            assert size==r['bytes'] and h.hexdigest()==r['sha256'],r['path']
        (dest/'FUNCTIONAL_EVIDENCE_MANIFEST.json').write_bytes(raw)
        (dest/'WINDOWS_PATH_MAP.json').write_text(json.dumps(aliases,indent=2),encoding='utf-8')
    report=dict(verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),archive=str(a.archive.resolve()),archive_sha256=archive_hash,verified_files=len(entries),destination=str(dest),all_files_verified=True,case_collision_path_map=aliases,interpretation='Original ZIP bytes and manifest paths are unchanged. Case-colliding Linux paths receive deterministic aliases only in the Windows extracted copy; both file contents are hash-verified.')
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
