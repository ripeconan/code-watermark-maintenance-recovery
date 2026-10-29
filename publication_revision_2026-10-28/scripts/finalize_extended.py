import json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT);start=time.time()
while True:
    log=(ROOT/'records/radius4_baseline.log').read_text()
    if 'EXTENDED_DONE structural_stress 216' in log:break
    if 'Traceback' in log:raise RuntimeError(log[-5000:])
    if time.time()-start>3600:raise TimeoutError('radius four incomplete')
    print('WAIT_RADIUS4',flush=True);time.sleep(30)
checked=0
for stem,base in [('confirmation','confirmation_augmented'),('structural_stress','structural_stress')]:
    before=list(map(json.loads,(ROOT/'results'/(base+'.jsonl')).read_text().splitlines()))
    after=list(map(json.loads,(ROOT/'results'/(stem+'_extended.jsonl')).read_text().splitlines()))
    assert len(before)==len(after)
    for a,b in zip(before,after):
        for group in b['groups'].values():
            for v in group['variants'].values():
                d=v['detection'];p=d['scores'].pop('l1_4');m=d['candidates'].pop('l1_4')
                assert p<=d['scores'].get('l1_3',1.)+1e-12
                assert m>=d['candidates'].get('l1_3',0)
                checked+=1
        assert a==b
(ROOT/'records/radius4_integrity.json').write_text(json.dumps(dict(unchanged_programs_and_previous_scores=True,nested_search_checks=checked),indent=2))
analysis='/home2/icdm/crosslingual-codewatermark/revision_20261019/.venv/bin/python'
runtime='/home2/icdm/crosslingual-codewatermark/upgrade_probe_20261019/.venv/bin/python'
subprocess.run([analysis,'scripts/analyze_confirmation.py'],check=True)
subprocess.run([analysis,'scripts/analyze_structural_stress.py'],check=True)
env=dict(os.environ,PYTHONPATH=str(ROOT/'tools/python'),PYTHONMALLOC='debug',PYTHONFAULTHANDLER='1')
subprocess.run([runtime,'scripts/verify_recovery_and_time.py'],check=True,env=env)
print('EXTENDED_FINAL_VERIFIED',checked,flush=True)
