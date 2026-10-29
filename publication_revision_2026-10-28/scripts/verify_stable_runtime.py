"""Repeat every final score under Python 3.11/tree-sitter 0.25.2, same grammars."""
import concurrent.futures,hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def one(path):
    from recovery_probe import init
    vendor=json.loads((ROOT/'records/tool_paths.json').read_text())['vendor'];init(vendor)
    from structural_recovery import score_code
    from recovery_detector import detect_recovery
    from add_delta_dictionary_baseline import init as di,work as dw
    from verify_additional_isolated import differences
    di(vendor,json.loads((ROOT/'records/context_delta_dictionary.json').read_text())['deltas'])
    old=json.loads(Path(path).read_text());new=json.loads(json.dumps(old));key=hashlib.sha256(('confirmation20261028|'+str(old['key'])).encode()).digest()
    for group in new['groups'].values():
        ctx=group['variants']['original']['detection']['context']
        for v in group['variants'].values():
            d=score_code(v['code'],new['language'],key,ctx)
            if ctx is None and v['detection'].get('scores',{}).get('oracle') is not None:
                d['scores']['oracle']=d['scores'].get('official',1.);d['candidates']['oracle']=1
            a=detect_recovery(v['code'],new['language'],key,'l1_4');d['scores']['l1_4']=a['min_p'];d['candidates']['l1_4']=a['candidates'];v['detection']=d
    new=dw(new);diff=differences(old,new);print(json.dumps(dict(differences=diff)))
    return int(bool(diff))

def run(row):
    env=dict(os.environ,PYTHONMALLOC='debug',PYTHONFAULTHANDLER='1',PYTHONPATH=str(ROOT/'tools/parser_stable'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    py='/home2/icdm/crosslingual-codewatermark/revision_20261019/.venv/bin/python'
    with tempfile.TemporaryDirectory(prefix='cwm-stable-audit-') as td:
        p=Path(td)/'input.json';p.write_text(json.dumps(row));r=subprocess.run([py,'-u',str(Path(__file__).resolve()),str(p)],capture_output=True,text=True,env=env,timeout=120)
    return dict(id=row['id'],language=row['language'],key=row['key'],returncode=r.returncode,stderr=r.stderr[-5000:],detail=json.loads(r.stdout) if r.stdout.strip() else None)

def main():
    rows=list(map(json.loads,(ROOT/'results/confirmation_extended.jsonl').read_text().splitlines()));start=time.time();results=[]
    with (ROOT/'records/stable_runtime_checks.jsonl').open('w') as f,concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for i,r in enumerate(ex.map(run,rows),1):
            f.write(json.dumps(r)+'\n');f.flush();results.append(r)
            if r['returncode']:print('STABLE_FAILURE',r,flush=True)
            if i%200==0:print('STABLE',i,len(rows),round(time.time()-start,1),flush=True)
    summary=dict(records=len(results),failures=sum(r['returncode']!=0 for r in results),python='3.11.15',tree_sitter='0.25.2')
    (ROOT/'records/stable_runtime_summary.json').write_text(json.dumps(summary,indent=2));print('STABLE_DONE',summary,flush=True)

if __name__=='__main__':sys.exit(one(sys.argv[1])) if len(sys.argv)>1 else main()
