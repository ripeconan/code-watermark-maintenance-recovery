"""Frozen detector evaluation on independent projects; no functional shortcuts."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse,collections,concurrent.futures,gzip,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
KEYS=(15485863,32452843,49979687)

def init():
    from replay_pilot import init as configure
    configure()

def score(code,lang,key,entries,oracle=None):
    from sew.sites.discovery import discover
    from sew.detect import detect
    from recovery_probe import grade_score,contexts
    from structural_recovery import syntax_candidates
    from structured_candidates import structured,nearest,dictionary
    start=time.perf_counter();tree,_,recs=discover(code,lang);official=detect(code,lang,key)
    if not recs:return dict(official=official,context=None,scores={},candidates={},coverage={},seconds=time.perf_counter()-start)
    observed=tuple(map(int,recs[0].sid[-1][4:].split('.')));grades=collections.defaultdict(list)
    for r in recs:grades[r.sid[:-1]].append(r.value)
    if len(grades)>256:return dict(official=official,context=observed,scores={},candidates={},coverage={},resource_abstention='over_256_grades',seconds=time.perf_counter()-start)
    s64,meta=structured(tree,observed,lang,64);s128,_=structured(tree,observed,lang,128)
    sets=dict(official={observed},syntax=syntax_candidates(tree,observed,lang),l1_4=set(contexts(observed,4)),
        nearest64=nearest(observed,64),nearest128=nearest(observed,128),structured64=s64,structured128=s128,
        dictionary64=dictionary(observed,entries),dictionary_pairs64=dictionary(observed,entries,combinations=True))
    if oracle is not None:sets['oracle']={tuple(oracle)}
    cache={c:grade_score(grades,c,key,lang) for c in set.union(*sets.values())}
    assert abs(cache[observed]-official['p'])<1e-12,'official parity failure'
    return dict(official=official,context=observed,scores={m:min(cache[c] for c in cs) for m,cs in sets.items()},
        candidates={m:len(cs) for m,cs in sets.items()},coverage={m:tuple(oracle) in cs for m,cs in sets.items()} if oracle is not None else {},
        pools=meta,seconds=time.perf_counter()-start)

def work(job):
    init()
    from sew.embed import embed
    from fine_replay import merge
    row=job['row'];key=hashlib.sha256(('confirmation20261028|'+str(job['key'])).encode()).digest()
    lang=row['language'];entries=job['dictionary'].get(lang,[]);start=time.time()
    r={k:v for k,v in row.items() if k not in ('before','after')};r.update(key=job['key'],group_scores={},functional_status='not_tested')
    codes=dict(negative_before=row['before'],negative_after=row['after'])
    for group,code in codes.items():r['group_scores'][group]=score(code,lang,key,entries)
    if row['split']=='calibration':
        r['seconds']=time.time()-start;return r
    em=embed(row['before'],lang,key);marked=em.pop('code');r['embedding']=em;codes['positive_before']=marked
    before=score(marked,lang,key,entries);r['group_scores']['positive_before']=before
    merged,detail=merge(row['before'],marked,row['after']);r['replay_detail']=detail
    r['merge_status']='clean' if merged is not None else 'conflict'
    if merged is not None:
        codes['positive_after']=merged;r['group_scores']['positive_after']=score(merged,lang,key,entries,before['context'])
        r['marked_context_changed']=before['context'] is not None and r['group_scores']['positive_after']['context'] is not None and before['context']!=r['group_scores']['positive_after']['context']
    r.update(codes=codes,seconds=time.time()-start)
    return r

def isolated(job):
    start=time.time()
    try:
        p=subprocess.run([sys.executable,__file__,'--worker'],input=json.dumps(job),capture_output=True,text=True,timeout=240)
        if p.returncode:raise RuntimeError(f'exit {p.returncode}: '+p.stderr[-1500:])
        return json.loads(p.stdout)
    except Exception as e:
        return {k:v for k,v in job['row'].items() if k not in ('before','after')}|dict(key=job['key'],error=type(e).__name__+': '+str(e),seconds=time.time()-start)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--worker',action='store_true');ap.add_argument('--split',choices=['development','calibration','test','all'],default='all');a=ap.parse_args()
    if a.worker:
        print(json.dumps(work(json.load(sys.stdin))));return
    from structured_candidates import fit_dictionary
    exposure=[json.loads(s) for s in (ROOT/'results/exposure.jsonl').read_text().splitlines() if s]
    learned=fit_dictionary(exposure)
    dp=ROOT/'records/development_dictionary.json'
    if dp.exists():assert json.loads(dp.read_text())==learned,'frozen dictionary changed'
    else:dp.write_text(json.dumps(learned,indent=2))
    selected={r['id'] for r in json.loads((ROOT/'records/replay_pilot_selection.json').read_text())}
    rows=[]
    for p in sorted((ROOT/'data/pairs').glob('*.gz')):
        rows.extend(r for r in json.loads(gzip.decompress(p.read_bytes())) if (a.split=='all' or r['split']==a.split) and (r['split']!='development' or r['id'] in selected))
    # Development runs first. Calibration/test specs are already frozen.
    rows.sort(key=lambda r:({'development':0,'calibration':1,'test':2}[r['split']],r['repo'],r['id']))
    out=ROOT/'results/upgrade_scores.jsonl';dest=ROOT/'data/upgrade_codes';dest.mkdir(parents=True,exist_ok=True)
    done={(r['id'],r['key']) for s in out.read_text().splitlines() if s and (r:=json.loads(s))} if out.exists() else set()
    jobs=[dict(row=r,key=k,dictionary=learned) for r in rows for k in KEYS if (r['id'],k) not in done]
    start=time.time()
    with out.open('a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        for i,r in enumerate(ex.map(isolated,jobs),1):
            codes=r.pop('codes',None)
            if codes:
                cp=dest/f"{r['id']}_{r['key']}.json.gz";cp.write_bytes(gzip.compress(json.dumps(codes).encode(),mtime=0));r['codes_file']=str(cp.relative_to(ROOT))
                r['code_sha256']={g:hashlib.sha256(c.encode()).hexdigest() for g,c in codes.items()}
            f.write(json.dumps(r)+'\n');f.flush()
            if i%30==0:print('UPGRADE',i,len(jobs),r['split'],r['repo'],'seconds',round(time.time()-start,1),flush=True)
    print('UPGRADE_DONE',len(jobs),round(time.time()-start,1),flush=True)

if __name__=='__main__':main()
