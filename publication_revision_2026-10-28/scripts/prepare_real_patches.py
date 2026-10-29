"""Prepare frozen public before/after text; no watermark scoring or execution."""
import gzip,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];old=ROOT.parent/'experiments/ecocal/data'
rows=[];errors=[]
for language in ('python','java'):
    for line in (old/('real_commits_'+language+'.jsonl')).read_text(encoding='utf8').split('\n'):
        if not line:continue
        r=json.loads(line)
        if not r['in_main']:continue
        tag=r['sha'][:12]+'__'+re.sub(r'[^A-Za-z0-9._-]','_',r['filename'])[:60]
        try:
            for part in ('before','after'):
                raw=(old/'raw'/language/(tag+'.'+part)).read_bytes().decode('utf8')
                candidates=[raw,raw.replace('\r\n','\n'),raw.replace('\r\r\n','\r\n')]
                code=next((c for c in candidates if hashlib.sha256(c.encode()).hexdigest()[:16]==r[part+'_sha256']),None)
                assert code is not None,part+' hash mismatch'
                r[part+'_cache_line_endings_restored']=(code!=raw)
                r[part]=code
            rows.append(r)
        except Exception as e:errors.append(dict(repo=r['repo'],sha=r['sha'],filename=r['filename'],error=str(e)))
payload=json.dumps(rows,ensure_ascii=False).encode();dest=ROOT/'data/real_patch_sources.json.gz'
dest.write_bytes(gzip.compress(payload))
(ROOT/'data/real_patch_preparation.json').write_text(json.dumps(dict(records=len(rows),errors=errors,
    sha256_uncompressed=hashlib.sha256(payload).hexdigest(),languages={l:sum(r['language']==l for r in rows) for l in ('python','java')}),indent=2))
print('REAL_PATCH_SOURCES',len(rows),'errors',len(errors),'compressed_bytes',dest.stat().st_size)
