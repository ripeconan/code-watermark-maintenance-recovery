"""Source/variant accounting, original-context coverage and runtime provenance."""
import collections,hashlib,importlib.metadata,json,platform,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
records=list(map(json.loads,(ROOT/'results/confirmation_augmented.jsonl').read_text().splitlines()))
checks=list(map(json.loads,(ROOT/'results/confirmation_functional.jsonl').read_text().splitlines()));assert len(checks)==693
tasks=json.loads((ROOT/'data/confirmation_tasks.json').read_text());func={}
for r in checks:
    for c in r['results']:func[r['language'],r['id'],c['sha256']]=c
out={};coverage=[];errors=[]
for lang in ('python','java','cpp'):
    rr=[r for r in records if r['language']==lang];tt=[t for t in tasks if t['language']==lang];rtest=[r for r in rr if r['split']=='test']
    source_test=[t for t in tt if t['split']=='test'];q=[func[lang,t['id'],hashlib.sha256(t['code'].encode()).hexdigest()] for t in source_test]
    marked=[func[lang,r['id'],r['groups']['positive']['variants']['original']['sha256']] for r in rtest if 'original' in r['groups']['positive']['variants']]
    out[lang]=dict(carriers=len(tt),valid=sum(t['split']=='valid' for t in tt),test=len(source_test),test_key_records=len(rtest),
        source_test_pass=sum(c.get('benchmark_pass',False) for c in q),source_compile_pass=sum(c.get('compile_ok',False) for c in q),
        marked_test_pass=sum(c.get('benchmark_pass',False) for c in marked),marked_compile_pass=sum(c.get('compile_ok',False) for c in marked),
        marked_preserved=sum(c.get('behavior_preserved',False) for c in marked),marked_available=len(marked),
        source_fail_statuses=dict(collections.Counter(c.get('error','test_or_completion_failure') for c in q if not c.get('benchmark_pass'))))
    for group in ('negative','positive'):
        for edit in ('original','formatter','helper','formatter_helper','helper_loop'):
            eligible=covered=available=0
            for r in rtest:
                vs=r['groups'][group]['variants'];orig=vs.get('original',{}).get('detection',{}).get('context');v=vs.get(edit)
                if v:
                    available+=1;d=v['detection'];eligible+=d['official']['n_grades']>=5;covered+=bool(orig is not None and orig in d.get('syntax_candidates',[]))
            coverage.append(dict(language=lang,group=group,edit=edit,n=len(rtest),available=available,eligible=eligible,original_context_in_syntax=covered))
for r in records:
    for group,g in r['groups'].items():
        if g['errors']:errors.append(dict(id=r['id'],language=r['language'],key=r['key'],group=group,errors=g['errors']))
packages={}
for name in ('tree-sitter','tree-sitter-python','tree-sitter-java','tree-sitter-cpp','black','numpy'):
    try:packages[name]=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:packages[name]='not_in_this_interpreter'
summary=dict(languages=out,coverage=coverage,variant_errors=errors,unique_problem_ids=len({t['id'] for t in tasks}),
    test_problem_ids=len({t['id'] for t in tasks if t['split']=='test'}),
    distinct_executed_programs=sum(len(r['results']) for r in checks),executed_test_cases=sum(len(c['cases']) for r in checks for c in r['results']),
    specified_fixtures=sum(len(t['tests']) for t in tasks),python=platform.python_version(),packages=packages,
    cpu=subprocess.run(['lscpu'],capture_output=True,text=True).stdout)
(ROOT/'results/study_metadata.json').write_text(json.dumps(summary,indent=2));print(json.dumps(out,indent=2));print('VARIANT_ERRORS',len(errors),flush=True)
