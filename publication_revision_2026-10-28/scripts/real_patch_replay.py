"""Counterfactual replay of frozen public developer patches on marked parents."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import concurrent.futures,gzip,hashlib,json,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
KEYS=(15485863,32452843,49979687)


def init(vendor):
    import recovery_probe
    recovery_probe.init(vendor)
    global embed,score_code
    from sew.embed import embed
    from structural_recovery import score_code


def work(job):
    source,k=job;key=hashlib.sha256(('confirmation20261028|'+str(k)).encode()).digest();lang=source['language']
    result={p:source[p] for p in ('repo','sha','parent_sha','filename','language','family','html_url') if p in source}
    result.update(key=k,group_scores={},group_errors={},merge_status='not_attempted');start=time.time()
    for group,code in [('negative_before',source['before']),('negative_after',source['after'])]:
        try:result['group_scores'][group]=score_code(code,lang,key)
        except Exception as e:result['group_errors'][group]=type(e).__name__+': '+str(e)
    try:
        em=embed(source['before'],lang,key);marked=em.pop('code');result['embedding']=em
        before=score_code(marked,lang,key);result['group_scores']['positive_before']=before
        with tempfile.TemporaryDirectory(prefix='cwm-patch-') as td:
            files=[Path(td)/s for s in ('marked','base','revised')]
            for p,text in zip(files,(marked,source['before'],source['after'])):p.write_text(text,encoding='utf8')
            merged=subprocess.run(['git','merge-file','-p',*map(str,files)],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=30)
        result['merge_returncode']=merged.returncode;result['merge_error']=merged.stderr[-1000:]
        result['merge_status']='clean' if merged.returncode==0 else ('conflict' if merged.returncode>0 else 'error')
        if merged.returncode==0:
            result['group_scores']['positive_after']=score_code(merged.stdout,lang,key,before['context'])
            result['merged_sha256']=hashlib.sha256(merged.stdout.encode()).hexdigest()
    except Exception as e:result['error']=type(e).__name__+': '+str(e)
    result['seconds']=time.time()-start
    return result


def main():
    paths=json.loads((ROOT/'records/tool_paths.json').read_text());data=gzip.decompress((ROOT/'data/real_patch_sources.json.gz').read_bytes())
    manifest=json.loads((ROOT/'data/real_patch_preparation.json').read_text());assert hashlib.sha256(data).hexdigest()==manifest['sha256_uncompressed']
    sources=json.loads(data);jobs=[(r,k) for r in sources for k in KEYS]
    dest=ROOT/'results/real_patch_replay.jsonl';start=time.time()
    with dest.open('w') as f,concurrent.futures.ProcessPoolExecutor(max_workers=2,initializer=init,initargs=(paths['vendor'],)) as ex:
        for i,r in enumerate(ex.map(work,jobs,chunksize=1),1):
            f.write(json.dumps(r)+'\n');f.flush()
            if i%10==0:print('PATCH',i,len(jobs),round(time.time()-start,1),flush=True)
    print('PATCH_DONE',len(jobs),round(time.time()-start,1),flush=True)


if __name__=='__main__':main()
