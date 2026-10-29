"""Prospective project-local confirmation, reusing the frozen v1 algorithms."""
import concurrent.futures,gzip,hashlib,json,time
from pathlib import Path
from evaluate_upgrade import isolated,KEYS
ROOT=Path(__file__).resolve().parents[1]

def main():
    learned=json.loads((ROOT/'records/development_dictionary.json').read_text())
    rows=[]
    for p in sorted((ROOT/'data/project_calibration').glob('*.json.gz')):
        if '.frame.' not in p.name:rows.extend(json.loads(gzip.decompress(p.read_bytes())))
    assert len({r['repo'] for r in rows})==4,'all four prospectively selected projects required'
    for repo in {r['repo'] for r in rows}:
        rr=[r for r in rows if r['repo']==repo]
        a=[r for r in rr if r['split']=='calibration'];b=[r for r in rr if r['split']=='test']
        assert not ({r['filename'] for r in a}&{r['filename'] for r in b})
        assert not ({r[k] for r in a for k in ('before_sha256','after_sha256')}&{r[k] for r in b for k in ('before_sha256','after_sha256')})
    rows.sort(key=lambda r:(r['split']!='calibration',r['repo'],r['id']))
    out=ROOT/'results/project_local_scores.jsonl';dest=ROOT/'data/project_local_codes';dest.mkdir(exist_ok=True)
    done={(r['id'],r['key']) for s in out.read_text().splitlines() if s and (r:=json.loads(s))} if out.exists() else set()
    jobs=[dict(row=r,key=k,dictionary=learned) for r in rows for k in KEYS if (r['id'],k) not in done]
    start=time.time()
    with out.open('a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        for i,r in enumerate(ex.map(isolated,jobs),1):
            codes=r.pop('codes',None)
            if codes:
                cp=dest/f"{r['id']}_{r['key']}.json.gz";cp.write_bytes(gzip.compress(json.dumps(codes).encode(),mtime=0))
                r['codes_file']=str(cp.relative_to(ROOT));r['code_sha256']={g:hashlib.sha256(c.encode()).hexdigest() for g,c in codes.items()}
            f.write(json.dumps(r)+'\n');f.flush()
            if i%30==0:print('PROJECT_LOCAL',i,len(jobs),r['repo'],round(time.time()-start,1),flush=True)
    print('PROJECT_LOCAL_DONE',len(jobs),round(time.time()-start,1),flush=True)

if __name__=='__main__':main()
