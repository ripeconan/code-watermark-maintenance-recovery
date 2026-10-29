"""Continue the frozen Java cohort after explicitly retained baseline failures."""
import concurrent.futures,datetime,json
from pathlib import Path
import test_java_runtime_v8 as recipe
base=recipe.base;ROOT=recipe.ROOT
ALLOWED={
    'd2c2ce4e3976b44aa1e6e064':('checkstyle/checkstyle','c7770ac969c1d078978801bf1cd5b2ce7ffdef0d',('run-checkstyle-files-generator','Failed processing OuterTypeNumberCheck','this.configs','ATNConfigSet.add')),
    '72ca443729da7ca9f23f3db9':('javaparser/javaparser','475a8464eac215657d9a3958f9b10e3e658bbcc6',('Compilation failure','GeneratedJavaParser.java','no suitable constructor found for ImportDeclaration')),
}

def main():
    frozen=json.loads((ROOT/'records/java_v8_freeze.json').read_text())
    assert frozen['ready'] and frozen['files']==recipe.provenance(),'frozen recipe changed'
    gate=json.loads((ROOT/'records/java_v8_original_gate.json').read_text())
    assert gate['original_jobs']==96 and set(gate['blocked_jobs'])==set(ALLOWED),gate
    out=ROOT/'results/functional_java_v8.jsonl'
    rows=[json.loads(s) for s in out.read_text().splitlines() if s]
    originals=[r for r in rows if r['original']]
    assert len(originals)==96 and len({r['job_id'] for r in rows})==len(rows)
    evidence=[Path(__file__),ROOT/'JAVA_V8_ORIGINAL_GATE_REVIEW.txt']
    for job_id,(repo,commit,tokens) in ALLOWED.items():
        record=next(r for r in originals if r['job_id']==job_id)
        assert record['commit']==commit and record['repo']==repo
        assert record['status']=='original_environment_unavailable'
        prep=ROOT/'records/environments_v4'/(repo.replace('/','__')+'__'+commit+'.json')
        original_prep=json.loads(prep.read_text())
        assert original_prep['status']=='failed' and original_prep['returncode']==1
        assert record['preparation']['source_preparation_sha256']==recipe.h(prep)
        logs=list((ROOT/'logs').glob('functional_v4*/'+prep.stem+'_prepare.log'))
        assert len(logs)==1
        text=logs[0].read_text(errors='replace')
        for token in tokens:assert token in text
        evidence.extend([prep,logs[0]])
    review=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        blocked_jobs=sorted(ALLOWED),disposition='retain original and linked marked versions as unavailable; preserve denominator; no test or recipe changes',
        files={str(p.relative_to(ROOT)):recipe.h(p) for p in evidence})
    (ROOT/'records/java_v8_original_gate_review.json').write_text(json.dumps(review,indent=2))
    base.VERSION='java_v8';base.PHASE='full';base.prepare=recipe.corrected_prepare
    jobs=[j for j in base.collect() if j['repo'] in recipe.REPOS]
    plan=json.loads((ROOT/'records/functional_jobs_java_v8.json').read_text())
    assert {j['job_id'] for j in jobs}=={j['job_id'] for j in plan}
    expected_original={j['job_id'] for j in jobs if j['original']}
    assert expected_original=={r['job_id'] for r in originals}
    done={r['job_id'] for r in rows};pending=[j for j in jobs if j['job_id'] not in done]
    assert all(not j['original'] for j in pending)
    with out.open('a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        for i,future in enumerate(concurrent.futures.as_completed([ex.submit(base.execute,j) for j in pending]),1):
            r=future.result();f.write(json.dumps(r)+'\n');f.flush()
            print('JAVA_V8_CONTINUED',i,len(pending),r['repo'],r['status'],r.get('counts'),round(r['total_seconds'],1),flush=True)
    (ROOT/'records/functional_complete_java_v8.txt').write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())

if __name__=='__main__':main()
