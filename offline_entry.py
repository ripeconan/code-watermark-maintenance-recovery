"""Run recorded analysis with portable NumPy-scalar JSON serialization."""
from pathlib import Path
import json,runpy,sys
import numpy as np

path=Path(sys.argv[1]).resolve()
original_default=json.JSONEncoder.default
def scalar_default(self,value):
    if isinstance(value,np.generic):return value.item()
    return original_default(self,value)
json.JSONEncoder.default=scalar_default
sys.path.insert(0,str(path.parent))
sys.argv=[str(path),*sys.argv[2:]]
runpy.run_path(str(path),run_name='__main__')
