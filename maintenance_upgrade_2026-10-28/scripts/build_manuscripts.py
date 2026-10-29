"""Compile both manuscripts; store build status without suppressing errors."""
import subprocess,json,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];paper=ROOT/'paper';out=[]
for name in ('main','supplement'):
    commands=[['pdflatex','-interaction=nonstopmode','-halt-on-error',name+'.tex']]
    if '\\bibliography' in (paper/(name+'.tex')).read_text():commands.append(['bibtex',name])
    commands += [['pdflatex','-interaction=nonstopmode','-halt-on-error',name+'.tex']]*2
    start=time.time()
    for i,command in enumerate(commands):
        p=subprocess.run(command,cwd=paper,capture_output=True,timeout=120)
        (ROOT/'records'/f'build_{name}_{i}.log').write_bytes(p.stdout+p.stderr)
        if p.returncode:raise RuntimeError((command,p.stdout[-2500:].decode(errors='replace')))
    log=(paper/(name+'.log')).read_text(errors='replace')
    warnings=[s for s in log.splitlines() if any(w in s for w in ('LaTeX Warning','Overfull','Undefined control'))]
    pdf=paper/(name+'.pdf');out.append(dict(name=name,seconds=time.time()-start,sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),warnings=warnings))
(ROOT/'records/build_final.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
