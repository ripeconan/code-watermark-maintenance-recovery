"""Repeat every marked carrier in a fresh debug-allocator Python process.

A long-running exploratory parser process raised an impossible Python iterator
error, consistent with an unresolved native/runtime problem seen in earlier
research. Do not dismiss it as a watermark outcome. This audit regenerates each
fixed embedding, edit and score independently; nonzero exits and differences
remain explicit failures. No failed case is silently retried or discarded.
"""
import argparse,concurrent.futures,json,os,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def one(path):
    from codecontests_study import init,work
    paths=json.loads((ROOT/'records/tool_paths.json').read_text());init(paths['vendor'],paths['java'],paths['clang'],paths['jar'])
    old=json.loads(Path(path).read_text());task=dict(id=old['id'],split=old['split'],language=old['language'],
        code=old['groups']['negative']['variants']['original']['code'])
    new=work((task,old['key']));differences=[];numeric_checks=0
    if old['embedding']!=new['embedding'] or old['embedding_error']!=new['embedding_error']:differences.append('embedding metadata')
    for group in ('negative','positive'):
        ov=old['groups'][group]['variants'];nv=new['groups'][group]['variants']
        if set(ov)!=set(nv):differences.append(group+' variant coverage')
        for edit in set(ov)&set(nv):
            a,b=ov[edit],nv[edit]
            if a['code']!=b['code'] or a['sha256']!=b['sha256']:differences.append(group+'/'+edit+' code')
            x,y=a['detection'],b['detection']
            for field in ('context','candidates','syntax_candidates'):
                if x.get(field)!=y.get(field):differences.append(group+'/'+edit+'/'+field)
            for field in ('n_grades','n_sites','k_grades','n_syntax','k_syntax','verdict'):
                if x['official'].get(field)!=y['official'].get(field):differences.append(group+'/'+edit+'/official/'+field)
            for name,value in x['scores'].items():
                numeric_checks+=1
                if name not in y['scores'] or abs(value-y['scores'][name])>1e-12:differences.append(group+'/'+edit+'/score/'+name)
    print(json.dumps(dict(id=old['id'],language=old['language'],key=old['key'],differences=differences,numeric_checks=numeric_checks)))
    return 1 if differences else 0


def run(row):
    python='/home2/icdm/crosslingual-codewatermark/upgrade_probe_20261019/.venv/bin/python'
    env=dict(os.environ,PYTHONMALLOC='debug',PYTHONFAULTHANDLER='1',PYTHONPATH=str(ROOT/'tools/python'),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='cwm-isolated-check-') as td:
        p=Path(td)/'expected.json';p.write_text(json.dumps(row))
        start=time.time()
        try:
            result=subprocess.run([python,'-u',str(Path(__file__).resolve()),'--one',str(p)],env=env,capture_output=True,text=True,timeout=120)
            try:detail=json.loads(result.stdout)
            except ValueError:detail={'stdout':result.stdout[-3000:]}
            return dict(id=row['id'],language=row['language'],key=row['key'],returncode=result.returncode,
                        stderr=result.stderr[-6000:],seconds=time.time()-start,detail=detail)
        except subprocess.TimeoutExpired as e:
            return dict(id=row['id'],language=row['language'],key=row['key'],returncode='timeout',seconds=time.time()-start)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--one');ap.add_argument('--workers',type=int,default=2);a=ap.parse_args()
    if a.one:return one(a.one)
    rows=[json.loads(s) for s in (ROOT/'results/confirmation.jsonl').read_text().split('\n') if s]
    dest=ROOT/'records/confirmation_isolated_checks.jsonl';done=set()
    if dest.exists():
        for s in dest.read_text().split('\n'):
            if s:
                r=json.loads(s);done.add((r['id'],r['language'],r['key']))
    jobs=[r for r in rows if (r['id'],r['language'],r['key']) not in done];start=time.time()
    with dest.open('a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i,r in enumerate(ex.map(run,jobs),1):
            f.write(json.dumps(r)+'\n');f.flush()
            if r['returncode']!=0:print('AUDIT_FAILURE',r['id'],r['language'],r['key'],r['returncode'],flush=True)
            if i%50==0:print('ISOLATED',i,len(jobs),round(time.time()-start,1),flush=True)
    records=[json.loads(s) for s in dest.read_text().split('\n') if s]
    failures=[r for r in records if r['returncode']!=0]
    summary=dict(cases=len(records),failures=len(failures),numeric_checks=sum(r.get('detail',{}).get('numeric_checks',0) for r in records),
                 failure_identities=[{k:r[k] for k in ('id','language','key','returncode')} for r in failures])
    (ROOT/'records/confirmation_isolated_summary.json').write_text(json.dumps(summary,indent=2));print('ISOLATED_DONE',summary,flush=True)
    return 1 if failures else 0


if __name__=='__main__':sys.exit(main())
