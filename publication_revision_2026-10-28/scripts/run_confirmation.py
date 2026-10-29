import argparse,json,subprocess,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['pilot','full','functional']);a=ap.parse_args()
paths=json.loads((ROOT/'records/tool_paths.json').read_text())
os.environ['PYTHONPATH']=paths.get('parser_packages',str(ROOT/'tools/python'))
python=paths.get('runtime_python','/home2/icdm/crosslingual-codewatermark/upgrade_probe_20261019/.venv/bin/python')
stem='confirmation_pilot' if a.phase=='pilot' else 'confirmation'
if a.phase!='functional':
    cmd=[python,'-u','scripts/codecontests_study.py','--vendor',paths['vendor'],'--java',paths['java'],'--clang',paths['clang'],'--jar',paths['jar'],'--workers','4']
    if a.phase=='pilot':cmd.append('--pilot')
    result=subprocess.run(cmd,cwd=ROOT)
    if result.returncode:sys.exit(result.returncode)
cmd=[python,'-u','scripts/confirmation_functional.py','--input',str(ROOT/'results'/(stem+'.jsonl')),
     '--out',str(ROOT/'results'/(stem+'_functional.jsonl')),'--jdk',paths['jdk'],'--workers','4']
sys.exit(subprocess.run(cmd,cwd=ROOT).returncode)
