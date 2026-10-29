"""Verify the public redacted artifact; optionally rerun its numerical analyses."""
from pathlib import Path
import argparse,collections,hashlib,json,os,shutil,subprocess,sys,tempfile
import numpy as np
ROOT=Path(__file__).resolve().parent
C='publication_revision_2026-10-28';M='maintenance_upgrade_2026-10-28';E='external_validity_2026-10-28'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1048576),b''):h.update(c)
 return h.hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--full',action='store_true');a=ap.parse_args()
 manifest=read(ROOT/'SHA256SUMS.json')
 for n,d in manifest.items():
  p=ROOT/n;assert p.is_file() and p.stat().st_size==d['bytes'] and sha(p)==d['sha256'],n
 assert len(read(ROOT/C/'data/selection_manifest.json'))==693
 temporal=[json.loads(s) for s in (ROOT/E/'results/temporal_scores.jsonl').read_text(encoding='utf8').splitlines() if s]
 assert len(temporal)==4125 and collections.Counter(r['split'] for r in temporal)=={'calibration':2064,'test':2061}
 decisions=read(ROOT/E/'robustness_revision_20261029/p2_decisions.json')
 assert len(decisions)==432 and sum(r['canonical_joint']['structured64'] for r in decisions)==183 and sum(r['line_joint']['structured64'] for r in decisions)==85
 p1=read(ROOT/E/'robustness_revision_20261029/p1_results.json');freeze=read(ROOT/E/'robustness_revision_20261029/p1_freeze.json')
 with np.load(ROOT/E/'robustness_revision_20261029/p1_draws.npz') as arrays:
  for budget in (20,40,80,'full'):
   metrics=np.mean([arrays[f'p{i}_b{budget}_metrics'].mean(axis=1) for i in range(6)],axis=0)
   for mi,method in enumerate(freeze['methods']):
    s=next(x for x in p1['summaries'] if x['scope']=='equal_project_mean' and x['method']==method and x['budget']==budget)
    for j,k in enumerate(('detection','alarm_lower','alarm_upper','infinite_threshold')):
     assert abs(s[k]['mean']-metrics[:,mi,j].mean())<1e-12
 report={'integrity_files':len(manifest),'controlled_carriers':693,'temporal_records':4125,'replay_attempts':432,'character_joint':183,'line_joint':85,'full':False}
 if a.full:
  env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONUTF8='1')
  with tempfile.TemporaryDirectory(prefix='watermark-public-') as tmp:
   out=Path(tmp)
   for base in (C,M,E):shutil.copytree(ROOT/base,out/base)
   def run(base,script,*args):
    command=[sys.executable,'-X','utf8',str(ROOT/'offline_entry.py'),str(out/base/'scripts'/script),*map(str,args)]
    print('RUN',base,script,flush=True)
    subprocess.run(command,check=True,cwd=out/base,env=env,stdout=subprocess.DEVNULL)
   def check(base,name):
    x=read(ROOT/base/'results'/name);y=read(out/base/'results'/name)
    assert x==y,base+'/'+name
   run(C,'analyze_confirmation.py');check(C,'confirmation_summary.json')
   for script,n in [('analyze_real_patches.py','real_patch_summary.json'),('analyze_structural_stress.py','structural_stress_summary.json'),('review_diagnostics.py','review_diagnostics.json')]:run(C,script);check(C,n)
   run(C,'correct_sew_verdicts.py','--input',out/C/'results/sew_generated_public.jsonl','--out',out/C/'results');check(C,'sew_corrected_summary.json')
   for script,n in [('analyze_upgrade.py','upgrade_summary.json'),('analyze_project_local.py','project_local_summary.json'),('analyze_functional.py','functional_summary.json'),('review_diagnostics.py','project_diagnostic_roc.json'),('calibration_source_control.py','calibration_source_control.json')]:run(M,script);check(M,n)
   run(E,'analyze_temporal.py');check(E,'temporal_summary.json')
   print('RUN finite-pool resampling',flush=True)
   subprocess.run([sys.executable,'-X','utf8',str(ROOT/'reproduce_budget.py'),str(out/E)],check=True,env=env,stdout=subprocess.DEVNULL)
  report.update(full=True,recomputed_summary_files=11)
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
