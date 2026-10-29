"""Exploratory detector-only context recovery on frozen SEW code (run on inner)."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import argparse, concurrent.futures, hashlib, itertools, json, sys, time
from collections import defaultdict
from pathlib import Path


def init(vendor):
    sys.path.insert(0, vendor)
    global discover, detect, target_bit, poibin_sf, load_q, FORMAT_RULE_IDS
    from sew.sites.discovery import discover
    from sew.detect import detect
    from sew.keying import target_bit
    from sew.stats import poibin_sf, load_q
    from sew.rules import FORMAT_RULE_IDS


def contexts(observed, radius):
    return sorted({tuple(a+b for a,b in zip(observed,delta))
                   for delta in itertools.product(range(-radius,radius+1),repeat=4)
                   if sum(map(abs,delta))<=radius
                   and all(a+b>=0 for a,b in zip(observed,delta))})


def grade_score(grades, ctx, key, language):
    q=load_q(language); h=[]; hs=[]; k=0; ks=0
    context='ctx:'+'.'.join(map(str,ctx))
    for head, vals in grades.items():
        target=target_bit(key,head+(context,))
        vote=int(2*sum(vals)>=len(vals)); hit=int(vote==target)
        qr=q.get(head[0],.5); prob=qr if target else 1-qr
        h.append(prob); k+=hit
        if head[0] not in FORMAT_RULE_IDS:hs.append(prob);ks+=hit
    p_all=poibin_sf(h,k) if h else 1.
    p_syn=poibin_sf(hs,ks) if hs else 1.
    return min(1.,2*min(p_all,p_syn))


def process(row):
    key=hashlib.sha256(('major20261027-sew-'+str(row['key'])).encode()).digest()
    result=[]
    for group in ('negative','positive'):
        original=row[group].get('original')
        old_ctx=None
        if original:
            _,_,old=discover(original['code'],'python')
            if old:old_ctx=tuple(map(int,old[0].sid[-1][4:].split('.')))
        for edit in ('original','formatter','strip_comments','dead_return'):
            start=time.perf_counter(); v=row[group].get(edit)
            r={k:row[k] for k in ('model','task_id','key','mode')}
            r.update(group=group,edit=edit,available=bool(v),correct=bool(v and v['test']['ok']),
                     source_correct=bool(row['negative'].get('original',{}).get('test',{}).get('ok')))
            if not v:
                r.update(n_grades=0,official=False,legacy=False,p=1.,scan1=1.,scan2=1.,bonf1=1.,bonf2=1.,oracle=1.,m1=0,m2=0)
                result.append(r);continue
            s=v['score']; r.update(n_grades=s['n_grades'],p=s['p'],
                official=s['verdict']=='Watermark detected', legacy=s['p']<.01)
            _,_,recs=discover(v['code'],'python');grades=defaultdict(list)
            for rec in recs:grades[rec.sid[:-1]].append(rec.value)
            assert len(grades)==s['n_grades'],(r,len(grades))
            if not recs:
                r.update(scan1=1.,scan2=1.,bonf1=1.,bonf2=1.,oracle=1.,m1=0,m2=0)
            else:
                ctx=tuple(map(int,recs[0].sid[-1][4:].split('.')))
                p0=grade_score(grades,ctx,key,'python')
                assert abs(p0-s['p'])<1e-12,(p0,s['p'],r)
                cache={c:grade_score(grades,c,key,'python') for c in contexts(ctx,2)}
                for radius in (1,2):
                    cs=contexts(ctx,radius); best=min(cache[c] for c in cs)
                    r['scan'+str(radius)]=best;r['bonf'+str(radius)]=min(1.,len(cs)*best)
                    r['m'+str(radius)]=len(cs)
                r.update(oracle=grade_score(grades,old_ctx,key,'python') if old_ctx else 1.,
                         context=list(ctx),original_context=list(old_ctx) if old_ctx else None)
            r['seconds']=time.perf_counter()-start;result.append(r)
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--vendor',required=True);ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
    rows=[r for line in Path(a.input).read_text().split('\n') if line and (r:=json.loads(line))['mode']=='official']
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    started=time.time()
    with out.open('w') as f,concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,initializer=init,initargs=(a.vendor,)) as ex:
        for i,chunk in enumerate(ex.map(process,rows,chunksize=4),1):
            for r in chunk:f.write(json.dumps(r)+'\n')
            f.flush()
            if i%64==0:print('PROGRESS',i,len(rows),round(time.time()-started,1),flush=True)
    print('DONE',len(rows),round(time.time()-started,1),flush=True)


if __name__=='__main__':main()
