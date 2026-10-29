"""Diagnostic only: compare retained grades and exclude inserted helper sites."""
import concurrent.futures,hashlib,json,os,subprocess,sys,tempfile,time
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def votes(recs):
    g=defaultdict(list)
    for r in recs:g[r.sid[:-1]].append(r.value)
    return {h:int(2*sum(v)>=len(v)) for h,v in g.items()}

def one(path):
    from recovery_probe import init
    init(json.loads((ROOT/'records/tool_paths.json').read_text())['vendor'])
    from sew.sites.discovery import discover
    from sew.sites.ctx import FUNC
    row=json.loads(Path(path).read_text());vs=row['groups']['positive']['variants'];out=[]
    if 'original' not in vs:print('[]');return
    tree,data,recs=discover(vs['original']['code'],row['language']);old=votes(recs)
    for edit in ('formatter','helper','formatter_helper','helper_loop'):
        v=vs.get(edit)
        if not v:continue
        tree,data,recs=discover(v['code'],row['language']);new=votes(recs);ranges=[];stack=[tree.root_node] if tree is not None else []
        while stack:
            n=stack.pop();stack.extend(n.children)
            if n.type in FUNC[row['language']]:
                name=n.child_by_field_name('name') or n.child_by_field_name('declarator')
                if name is not None and b'wmMaintenanceHelper' in data[name.start_byte:name.end_byte]:ranges.append((n.start_byte,n.end_byte))
        retained=[r for r in recs if not any(a<=r.span[0] and r.span[1]<=b for a,b in ranges)]
        clean=votes(retained);common=set(old)&set(new);common_clean=set(old)&set(clean)
        out.append(dict(id=row['id'],language=row['language'],key=row['key'],edit=edit,parse_available=tree is not None,original_grades=len(old),edited_grades=len(new),
            common_grades=len(common),changed_common_votes=sum(old[h]!=new[h] for h in common),
            excluded_helper_sites=len(recs)-len(retained),excluded_helper_functions=len(ranges),retained_grades=len(clean),
            retained_common_grades=len(common_clean),changed_retained_votes=sum(old[h]!=clean[h] for h in common_clean),
            dropped_original_heads=len(set(old)-set(clean)),new_retained_heads=len(set(clean)-set(old))))
    print(json.dumps(out))

def run(row):
    env=dict(os.environ,PYTHONMALLOC='debug',PYTHONFAULTHANDLER='1',PYTHONPATH=os.environ.get('CWM_PARSER_PATH',str(ROOT/'tools/python')),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    py=os.environ.get('CWM_RUNTIME_PYTHON','/home2/icdm/crosslingual-codewatermark/upgrade_probe_20261019/.venv/bin/python')
    with tempfile.TemporaryDirectory(prefix='cwm-mechanism-') as td:
        p=Path(td)/'row.json';p.write_text(json.dumps(row));r=subprocess.run([py,'-u',str(Path(__file__).resolve()),str(p)],env=env,capture_output=True,text=True,timeout=120)
        if r.returncode:raise RuntimeError((row['id'],row['language'],r.stderr[-4000:]))
        return json.loads(r.stdout)

def main():
    rows=[r for r in map(json.loads,(ROOT/'results/confirmation_extended.jsonl').read_text().splitlines()) if r['split']=='test'];out=[];start=time.time()
    with (ROOT/'results/grade_mechanism_rows.jsonl').open('w') as f,concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        for i,chunk in enumerate(ex.map(run,rows),1):
            out+=chunk
            for r in chunk:f.write(json.dumps(r)+'\n')
            f.flush()
            if i%150==0:print('MECHANISM',i,len(rows),round(time.time()-start,1),flush=True)
    summary=[]
    for lang in ('python','java','cpp'):
        for edit in ('formatter','helper','formatter_helper','helper_loop'):
            rr=[r for r in out if r['language']==lang and r['edit']==edit]
            fields=('original_grades','edited_grades','common_grades','changed_common_votes','excluded_helper_sites','retained_common_grades','changed_retained_votes','dropped_original_heads','new_retained_heads')
            summary.append(dict(language=lang,edit=edit,n=len(rr),parse_failures=sum(not r['parse_available'] for r in rr),**{k:sum(r[k] for r in rr) for k in fields},
                records_with_retained_vote_change=sum(r['changed_retained_votes']>0 for r in rr),
                records_with_common_vote_change=sum(r['changed_common_votes']>0 for r in rr)))
    (ROOT/'results/grade_mechanism_summary.json').write_text(json.dumps(summary,indent=2));print('MECHANISM_DONE',len(rows),flush=True)

if __name__=='__main__':one(sys.argv[1]) if len(sys.argv)>1 else main()
