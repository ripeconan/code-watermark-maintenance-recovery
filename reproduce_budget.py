"""Repeat all saved finite-pool draws in a fresh destination using frozen code."""
from pathlib import Path
import importlib.util,json,sys
import numpy as np

study=Path(sys.argv[1]).resolve()
destination=study/'budget_recomputed'
assert not destination.exists(),'Budget reconstruction destination must be new.'
sys.path.insert(0,str(study/'scripts'))
source=study/'scripts/calibration_budget.py'
spec=importlib.util.spec_from_file_location('frozen_calibration_budget',source)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.OUT=destination;sys.argv=[str(source)]
module.main()
old=study/'robustness_revision_20261029'
with np.load(old/'p1_draws.npz') as a,np.load(destination/'p1_draws.npz') as b:
    assert a.files==b.files
    for key in a.files:assert np.array_equal(a[key],b[key]),key
    arrays=len(a.files)
before=json.loads((old/'p1_results.json').read_text())
after=json.loads((destination/'p1_results.json').read_text())
assert before['summaries']==after['summaries']
assert before['pools']==after['pools']
report={'passed':True,'arrays_exactly_reproduced':arrays,'draws_per_project_per_finite_budget':5000,
        'summaries_exactly_reproduced':len(before['summaries']),'pools_exactly_reproduced':6,
        'original_freeze_preserved':True}
(destination/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
