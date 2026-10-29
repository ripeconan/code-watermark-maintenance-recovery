"""Wait for complete experiment files, analyze, and require independent audits."""
import json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT)
analysis='/home2/icdm/crosslingual-codewatermark/revision_20261019/.venv/bin/python'
runtime='/home2/icdm/crosslingual-codewatermark/upgrade_probe_20261019/.venv/bin/python'
def count(p):
    return len(p.read_text().splitlines()) if p.exists() else 0
start=time.time()
while count(ROOT/'results/confirmation_functional.jsonl')<693:
    if time.time()-start>3600:raise TimeoutError('functional study incomplete')
    print('WAIT_FUNCTIONAL',count(ROOT/'results/confirmation_functional.jsonl'),flush=True);time.sleep(30)
subprocess.run([analysis,'scripts/analyze_confirmation.py'],check=True)
subprocess.run([analysis,'scripts/analyze_real_patches.py'],check=True)
subprocess.run([analysis,'scripts/analyze_structural_stress.py'],check=True)
env=dict(os.environ,PYTHONPATH=str(ROOT/'tools/python'))
subprocess.run([runtime,'scripts/study_metadata.py'],check=True,env=env)
while not (ROOT/'records/confirmation_isolated_summary.json').exists():
    if time.time()-start>3600:raise TimeoutError('independent audit incomplete')
    print('WAIT_AUDIT',flush=True);time.sleep(30)
a=json.loads((ROOT/'records/confirmation_isolated_summary.json').read_text());assert a['cases']==2079 and a['failures']==0,a
b=json.loads((ROOT/'records/additional_isolated_summary.json').read_text());assert all(r['failures']==0 for r in b.values()),b
s=json.loads((ROOT/'results/confirmation_summary.json').read_text());assert s['missing_functional']==0
print('FINAL_ANALYSIS_AND_AUDITS_PASSED',flush=True)
