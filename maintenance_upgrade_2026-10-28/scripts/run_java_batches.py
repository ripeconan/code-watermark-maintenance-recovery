"""Finish the preselected Java cohort, with revision groups in isolated workers."""
import collections,concurrent.futures,json,multiprocessing,time
from pathlib import Path
import test_project_local as harness
ROOT=Path(__file__).resolve().parents[1]
def group_work(jobs):
    harness.RUN_ID='javabatch';paths=json.loads((ROOT/'records/tool_paths.json').read_text());records=[]
    outdir=ROOT/'results/java_job_records';outdir.mkdir(exist_ok=True)
    for j in jobs:
        dest=outdir/(j['job_id']+'.json')
        if dest.exists():r=json.loads(dest.read_text())
        else:
            start=time.time()
            try:r=harness.test(j,paths)
            except Exception as e:r=dict(status='harness_error',pass_tests=False,error=type(e).__name__+': '+str(e))
            r={k:v for k,v in j.items() if k!='code'}|r|dict(total_seconds=time.time()-start)
            temporary=dest.with_suffix('.tmp');temporary.write_text(json.dumps(r));temporary.replace(dest)
            print('JAVA_JOB',j['repo'],j['job_id'],r['status'],r.get('counts'),round(time.time()-start,1),flush=True)
        records.append(r)
    return records
def main():
    out=ROOT/'results/project_local_tests_javabatch.jsonl';done=set()
    for p in (out,ROOT/'results/project_local_tests_javaprovider.jsonl'):
        if p.exists():done.update(json.loads(s)['job_id'] for s in p.read_text().splitlines() if s)
    groups=collections.defaultdict(list)
    for j in harness.collect():
        if j['language']=='java' and j['job_id'] not in done:groups[j['repo'],j['commit']].append(j)
    print('JAVA_BATCH_START',len(groups),sum(map(len,groups.values())),flush=True)
    with out.open('a') as f,concurrent.futures.ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn')) as ex:
        for records in ex.map(group_work,list(groups.values())):
            for r in records:f.write(json.dumps(r)+'\n');f.flush()
    print('JAVA_BATCH_DONE',flush=True)
if __name__=='__main__':main()
