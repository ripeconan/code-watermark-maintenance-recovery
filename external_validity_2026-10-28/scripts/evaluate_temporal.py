"""Frozen detector, checkpointed stages, independent temporal validation data."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import argparse, concurrent.futures, gzip, hashlib, json, subprocess, sys, tempfile, time, traceback
from pathlib import Path
from evaluate_upgrade import KEYS, init, score

ROOT=Path(__file__).resolve().parents[1]

def checkpoint(path, result):
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(result))
    temp.replace(path)

def work(job, saved):
    init()
    from sew.embed import embed
    from fine_replay import merge
    row=job['row']; lang=row['language']; start=time.time()
    key=hashlib.sha256(('confirmation20261028|'+str(job['key'])).encode()).digest()
    entries=job['dictionary'].get(lang,[])
    result={k:v for k,v in row.items() if k not in ('before','after')}
    result.update(key=job['key'],group_scores={},stage_status={},codes={},functional_status='not_tested')
    def save():
        result['seconds']=time.time()-start; checkpoint(saved,result)
    save()
    for group, code in [('negative_before',row['before']),('negative_after',row['after'])]:
        result['active_stage']=group; save()
        result['codes'][group]=code
        try:
            result['group_scores'][group]=score(code,lang,key,entries)
            result['stage_status'][group]='completed'
        except Exception as e:
            result['stage_status'][group]='error'
            result.setdefault('stage_errors',{})[group]=type(e).__name__+': '+str(e)
        save()
    if row['split']=='calibration':
        result['active_stage']='done';save();return result
    result['active_stage']='embedding';save()
    try:
        em=embed(row['before'],lang,key);marked=em.pop('code')
        result['embedding']=em;result['codes']['positive_before']=marked
        result['stage_status']['embedding']='completed';save()
        result['active_stage']='positive_before';save()
        before=score(marked,lang,key,entries)
        result['group_scores']['positive_before']=before
        result['stage_status']['positive_before']='completed';save()
        result['active_stage']='replay';save()
        merged, detail=merge(row['before'],marked,row['after'])
        result['replay_detail']=detail
        result['merge_status']='clean' if merged is not None else 'conflict'
        result['stage_status']['replay']='completed';save()
        if merged is not None:
            result['codes']['positive_after']=merged
            result['active_stage']='positive_after';save()
            after=score(merged,lang,key,entries,before['context'])
            result['group_scores']['positive_after']=after
            result['marked_context_changed']=before['context'] is not None and after['context'] is not None and before['context']!=after['context']
            result['stage_status']['positive_after']='completed';save()
    except Exception as e:
        stage=result['active_stage'];result['stage_status'][stage]='error'
        result.setdefault('stage_errors',{})[stage]=type(e).__name__+': '+str(e)
    result['active_stage']='done';save();return result

def isolated(job):
    start=time.time()
    with tempfile.TemporaryDirectory(prefix='score-',dir=ROOT/'work') as td:
        saved=Path(td)/'checkpoint.json'
        try:
            p=subprocess.run([sys.executable,__file__,'--worker',str(saved)],input=json.dumps(job),capture_output=True,text=True,timeout=240)
            if p.returncode:
                raise RuntimeError(f'exit {p.returncode}: '+p.stderr[-1500:])
            return json.loads(saved.read_text())
        except Exception as e:
            result=json.loads(saved.read_text()) if saved.exists() else {k:v for k,v in job['row'].items() if k not in ('before','after')}
            result.update(key=job['key'],error=type(e).__name__+': '+str(e),seconds=time.time()-start)
            result.setdefault('stage_status',{})[result.get('active_stage','initialization')]='process_error'
            return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--worker');ap.add_argument('--limit',type=int);a=ap.parse_args()
    if a.worker:
        work(json.load(sys.stdin),Path(a.worker));return
    assert (ROOT/'records/scoring_freeze.json').exists(),'freeze provenance before scoring'
    assert json.loads((ROOT/'records/parity_check.json').read_text())['passed'],'frozen detector parity required'
    dictionary=json.loads((ROOT/'records/development_dictionary.json').read_text())
    manifests=json.loads((ROOT/'records/acquisition_summary.json').read_text())
    assert len(manifests)==6 and all(r.get('complete') for r in manifests)
    rows=[r for p in sorted((ROOT/'data/pairs').glob('*.json.gz')) if '.frame.' not in p.name for r in json.loads(gzip.decompress(p.read_bytes()))]
    assert len({r['id'] for r in rows})==len(rows)
    rows.sort(key=lambda r:(r['split']!='calibration',r['repo'],r['timestamp'],r['id']))
    out=ROOT/'results/temporal_scores.jsonl';dest=ROOT/'data/codes';dest.mkdir(parents=True,exist_ok=True)
    done={(r['id'],r['key']) for s in out.read_text().splitlines() if s and (r:=json.loads(s))} if out.exists() else set()
    jobs=[dict(row=r,key=k,dictionary=dictionary) for r in rows for k in KEYS if (r['id'],k) not in done]
    if a.limit:jobs=jobs[:a.limit]
    start=time.time()
    with out.open('a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        for i,r in enumerate(ex.map(isolated,jobs),1):
            codes=r.pop('codes',None)
            if codes:
                cp=dest/f"{r['id']}_{r['key']}.json.gz"
                cp.write_bytes(gzip.compress(json.dumps(codes).encode(),mtime=0))
                r['codes_file']=str(cp.relative_to(ROOT));r['code_sha256']={g:hashlib.sha256(c.encode()).hexdigest() for g,c in codes.items()}
            f.write(json.dumps(r)+'\n');f.flush()
            if i%30==0:print('TEMPORAL',i,len(jobs),r['repo'],r['split'],round(time.time()-start,1),flush=True)
    print('SCORING_COMPLETE',len(jobs),round(time.time()-start,1),flush=True)

if __name__=='__main__':
    main()
