"""Pinned public carriers, paired maintenance interventions, blind recovery.

Run on inner. This script does NOT execute source programs. The separate harness
executes deduplicated sources in a network-isolated filesystem sandbox.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse,concurrent.futures,hashlib,json,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
KEYS=(15485863,32452843,49979687)


def init(vendor,java,clang,jar):
    import recovery_probe
    recovery_probe.init(vendor)
    global embed,discover,score_code,JAVA,CLANG,JAR
    from sew.embed import embed
    from sew.sites.discovery import discover
    from structural_recovery import score_code
    JAVA,CLANG,JAR=java,clang,jar


def sha(code):return hashlib.sha256(code.encode()).hexdigest()


def helper(code,language,loop=False):
    name='wmMaintenanceHelper'+sha(code)[:12]
    assert name not in code
    if language=='python':
        body=('    for wmMaintenanceIndex in range(0):\n        pass\n' if loop else '')
        return code+'\n\ndef '+name+'(value):\n'+body+'    return value\n'
    body=('for (int wmMaintenanceIndex=0; wmMaintenanceIndex<0; ++wmMaintenanceIndex) {} ' if loop else '')
    if language=='cpp':return code+'\nstatic int '+name+'(int value) { '+body+'return value; }\n'
    tree,data,_=discover(code,language)
    stack=[tree.root_node];classes=[]
    while stack:
        n=stack.pop();stack.extend(n.children)
        if n.type=='class_declaration' and n.parent.type=='program':classes.append(n)
    if not classes:raise ValueError('no top-level class for unused Java helper')
    cls=min(classes,key=lambda n:n.start_byte);block=cls.child_by_field_name('body')
    assert block is not None
    at=block.end_byte-1
    inserted=('\nprivate static int '+name+'(int value) { '+body+'return value; }\n').encode()
    return (data[:at]+inserted+data[at:]).decode()


def format_code(code,language):
    if language=='python':
        import black
        return black.format_str(code,mode=black.Mode(line_length=88))
    cmd=[CLANG,'--style=Google'] if language=='cpp' else [JAVA,'-jar',JAR,'-']
    r=subprocess.run(cmd,input=code,text=True,encoding='utf-8',capture_output=True,timeout=25)
    if r.returncode:raise ValueError('formatter: '+r.stderr[-500:])
    return r.stdout


def variants(code,language):
    variants={'original':code};errors={}
    for name,fn in [('formatter',lambda:format_code(code,language)),('helper',lambda:helper(code,language)),
                    ('helper_loop',lambda:helper(code,language,True))]:
        try:variants[name]=fn()
        except Exception as e:errors[name]=type(e).__name__+': '+str(e)
    if 'formatter' in variants:
        try:variants['formatter_helper']=helper(variants['formatter'],language)
        except Exception as e:errors['formatter_helper']=str(e)
        # Tool idempotence is recorded rather than silently assuming a normal form.
        try:
            if format_code(variants['formatter'],language)!=variants['formatter']:errors['formatter_idempotence']='not idempotent'
        except Exception as e:errors['formatter_idempotence']=str(e)
    return variants,errors


def work(job):
    task,key_id=job;lang=task['language'];key=hashlib.sha256(('confirmation20261028|'+str(key_id)).encode()).digest()
    source=task['code'];start=time.time()
    try:
        embedding=embed(source,lang,key);marked=embedding.pop('code');error=None
    except Exception as e:
        embedding={};marked=None;error=type(e).__name__+': '+str(e)
    result={'id':task['id'],'split':task['split'],'language':lang,'key':key_id,'source_sha256':sha(source),
            'embedding':embedding,'embedding_error':error,'groups':{}}
    for group,code in [('negative',source),('positive',marked)]:
        if code is None:
            result['groups'][group]={'variants':{},'errors':{'embedding':error}};continue
        vs,errors=variants(code,lang);out={}
        original=score_code(code,lang,key);original_ctx=original['context']
        for edit,text in vs.items():
            score=original if edit=='original' else score_code(text,lang,key,original_ctx)
            if edit=='original':score['scores']['oracle']=score['scores'].get('official',1.);score['candidates']['oracle']=1
            out[edit]={'code':text,'sha256':sha(text),'detection':score}
        result['groups'][group]={'variants':out,'errors':errors}
    result['seconds']=time.time()-start
    return result


def prepare():
    import pyarrow.parquet as pq
    sel=json.loads((ROOT/'data/codecontests_selection.json').read_text())
    splits={}
    for split in ('valid','test'):
        p=next((ROOT/'data/codecontests').glob(split+'-*.parquet'));splits[split]=pq.read_table(p).to_pylist()
    tasks=[]
    for lang,entries in sel.items():
        for pid,ix in entries:
            _,split,index=pid.split('/');r=splits[split][int(index)];code=r['solutions']['solution'][ix]
            assert r['solutions']['language'][ix]=={'python':3,'cpp':2,'java':4}[lang]
            tests=[]
            for i,(inp,out) in enumerate(zip(r['public_tests']['input'],r['public_tests']['output'])):
                tests.append(dict(kind='public',index=i,input=inp,output=out))
            extra=[]
            for kind in ('private_tests','generated_tests'):
                for i,(inp,out) in enumerate(zip(r[kind]['input'],r[kind]['output'])):
                    extra.append(dict(kind=kind,index=i,input=inp,output=out))
            extra.sort(key=lambda t:sha(pid+'|'+t['kind']+'|'+str(t['index'])))
            tests+=extra[:8]
            tasks.append(dict(id=pid,split=split,language=lang,solution_index=ix,code=code,tests=tests,
                              source_name=r['name'],input_file=r.get('input_file',''),output_file=r.get('output_file','')))
    p=ROOT/'data/confirmation_tasks.json';p.write_text(json.dumps(tasks,ensure_ascii=False),encoding='utf-8')
    print('PREPARED',len(tasks),{l:sum(t['language']==l for t in tasks) for l in sel},flush=True)
    return tasks


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--vendor',required=True);ap.add_argument('--java',required=True)
    ap.add_argument('--clang',required=True);ap.add_argument('--jar',required=True);ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--prepare-only',action='store_true');ap.add_argument('--pilot',action='store_true');a=ap.parse_args()
    p=ROOT/'data/confirmation_tasks.json';tasks=json.loads(p.read_text(encoding='utf-8')) if p.exists() and p.stat().st_size else prepare()
    if a.prepare_only:return
    if a.pilot:
        # Engineering-only cases from calibration split; final test split untouched.
        tasks=[next(t for t in tasks if t['language']==l and t['split']=='valid') for l in ('python','java','cpp')]
    dest=ROOT/'results'/('confirmation_pilot.jsonl' if a.pilot else 'confirmation.jsonl');done=set()
    if dest.exists():
        for line in dest.read_text().split('\n'):
            if line:
                r=json.loads(line);done.add((r['id'],r['language'],r['key']))
    jobs=[(t,k) for t in tasks for k in (KEYS[:1] if a.pilot else KEYS) if (t['id'],t['language'],k) not in done]
    print('READY',len(jobs),flush=True);start=time.time()
    with dest.open('a') as f,concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,initializer=init,initargs=(a.vendor,a.java,a.clang,a.jar)) as ex:
        for i,r in enumerate(ex.map(work,jobs,chunksize=1),1):
            f.write(json.dumps(r,ensure_ascii=False)+'\n');f.flush()
            if i%20==0 or a.pilot:print('PROGRESS',i,len(jobs),round(time.time()-start,1),flush=True)
    print('DONE',len(jobs),round(time.time()-start,1),flush=True)


if __name__=='__main__':main()
