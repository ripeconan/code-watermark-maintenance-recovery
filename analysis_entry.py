"""Load the unchanged selection function without Linux execution-harness imports.

This adapter is only for two offline ledger-analysis scripts. It extracts the
original sha/selected_rows AST verbatim; it does not replace experiment outputs
or pretend that the resource-isolation harness runs on Windows.
"""
import ast,gzip,hashlib,json,runpy,sys,types
from pathlib import Path

path=Path(sys.argv[1]).resolve()
assert path.name in ('verify_functional_final.py','summarize_functional_final.py')
root=path.parent.parent
source=path.parent/'test_temporal.py'
tree=ast.parse(source.read_text(encoding='utf-8'))
functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('sha','selected_rows')]
assert {n.name for n in functions}=={'sha','selected_rows'}
module=types.ModuleType('test_temporal')
module.__dict__.update(ROOT=root,json=json,gzip=gzip,hashlib=hashlib)
exec(compile(ast.Module(body=functions,type_ignores=[]),str(source),'exec'),module.__dict__)
sys.modules['test_temporal']=module
sys.path.insert(0,str(path.parent))
sys.argv=[str(path),*sys.argv[2:]]
runpy.run_path(str(path),run_name='__main__')
