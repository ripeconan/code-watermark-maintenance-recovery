"""Exploratory, outcome-independent boundary sample; fixed confirmation thresholds."""
import concurrent.futures,hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def nested(code,lang):
    from codecontests_study import discover,sha
    name='wmNestedHelper'+sha(code)[:12];assert name not in code
    if lang=='python':
        return code+'\n\ndef '+name+'(a, b):\n    for wmI in range(0):\n        for wmJ in range(0):\n            pass\n    if a < 0:\n        return b\n    return a\n'
    text='static int '+name+'(int a, int b) { for (int wmI=0; wmI<0; ++wmI) { for (int wmJ=0; wmJ<0; ++wmJ) {} } if (a<0) { return b; } return a; }'
    if lang=='cpp':return code+'\n'+text+'\n'
    tree,data,_=discover(code,lang);stack=[tree.root_node];classes=[]
    while stack:
        n=stack.pop();stack.extend(n.children)
        if n.type=='class_declaration' and n.parent.type=='program':classes.append(n)
    cls=min(classes,key=lambda n:n.start_byte);at=cls.child_by_field_name('body').end_byte-1
    return (data[:at]+('\nprivate '+text+'\n').encode()+data[at:]).decode()

def one(path):
    from codecontests_study import sha
    # Module globals are bound only after init; import the module for score_code.
    import codecontests_study as study
    p=json.loads((ROOT/'records/tool_paths.json').read_text());study.init(p['vendor'],p['java'],p['clang'],p['jar'])
    from add_delta_dictionary_baseline import init as di,work as dw
    di(p['vendor'],json.loads((ROOT/'records/context_delta_dictionary.json').read_text())['deltas'])
    r=json.loads(Path(path).read_text());key=hashlib.sha256(('confirmation20261028|'+str(r['key'])).encode()).digest()
    for group in r['groups'].values():
        original=group['variants'].get('original');group['variants']={};group['errors']={}
        if not original:continue
        for edit,fn in [('nested_helper',lambda c:nested(c,r['language'])),('two_helpers',lambda c:study.helper(study.helper(c,r['language']),r['language']))]:
            try:
                code=fn(original['code']);d=study.score_code(code,r['language'],key,original['detection']['context'])
                group['variants'][edit]=dict(code=code,sha256=sha(code),detection=d)
            except Exception as e:group['errors'][edit]=type(e).__name__+': '+str(e)
    r=dw(r);print(json.dumps(r));return 0

def run(row):
    env=dict(os.environ,PYTHONMALLOC='debug',PYTHONFAULTHANDLER='1',PYTHONPATH=str(ROOT/'tools/python'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    py='/home2/icdm/crosslingual-codewatermark/upgrade_probe_20261019/.venv/bin/python'
    with tempfile.TemporaryDirectory(prefix='cwm-stress-') as td:
        f=Path(td)/'input.json';f.write_text(json.dumps(row))
        r=subprocess.run([py,'-u',str(Path(__file__).resolve()),str(f)],env=env,capture_output=True,text=True,timeout=120)
        if r.returncode:raise RuntimeError((row['id'],row['language'],row['key'],r.stderr[-5000:]))
        return json.loads(r.stdout)

def main():
    rows=list(map(json.loads,(ROOT/'results/confirmation_augmented.jsonl').read_text().splitlines()));selected=[]
    for lang in ('python','java','cpp'):
        ids=sorted({r['id'] for r in rows if r['language']==lang and r['split']=='test'},key=lambda x:hashlib.sha256(('stress|'+x).encode()).hexdigest())[:24]
        selected.extend(r for r in rows if r['language']==lang and r['id'] in ids)
    assert len(selected)==216
    (ROOT/'records/stress_selection.json').write_text(json.dumps([{k:r[k] for k in ('id','language','key')} for r in selected],indent=2))
    with (ROOT/'results/structural_stress.jsonl').open('w') as f,concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        for i,r in enumerate(ex.map(run,selected),1):
            f.write(json.dumps(r)+'\n');f.flush()
            if i%24==0:print('STRESS',i,216,flush=True)
    p=json.loads((ROOT/'records/tool_paths.json').read_text());py='/home2/icdm/crosslingual-codewatermark/upgrade_probe_20261019/.venv/bin/python'
    return subprocess.run([py,'-u',str(ROOT/'scripts/confirmation_functional.py'),'--input',str(ROOT/'results/structural_stress.jsonl'),
        '--out',str(ROOT/'results/structural_stress_functional.jsonl'),'--jdk',p['jdk'],'--workers','4']).returncode

if __name__=='__main__':sys.exit(one(sys.argv[1]) if len(sys.argv)>1 else main())
