"""Private Ubuntu LuaTeX data overlay; never changes system packages."""
import datetime,hashlib,json,os,subprocess,tempfile
from pathlib import Path
from test_temporal import ROOT,sandbox
from run_project_tests import run_limited

PACKAGE='texlive-luatex'
VERSION='2021.20220204-1'
EXPECTED='617e3a1193c654b02a454c7d2c9d3c5715631efd2486cb7728054d353cbc8216'

def main():
    dest=ROOT/'tools/sphinx_tex_addons';packages=dest/'packages';overlay=dest/'root'
    packages.mkdir(parents=True,exist_ok=True);overlay.mkdir(exist_ok=True)
    metadata=subprocess.check_output(['apt-cache','show',PACKAGE+'='+VERSION],text=True)
    (ROOT/'records/sphinx_luatex_package_metadata.txt').write_text(metadata)
    assert 'SHA256: '+EXPECTED in metadata
    deb=packages/f'{PACKAGE}_{VERSION}_all.deb'
    if not deb.exists():
        subprocess.run(['apt-get','download',PACKAGE+'='+VERSION],cwd=packages,check=True,timeout=300)
    digest=hashlib.sha256(deb.read_bytes()).hexdigest();assert digest==EXPECTED
    subprocess.run(['dpkg-deb','-x',str(deb),str(overlay)],check=True,timeout=60)
    tree=overlay/'usr/share/texlive/texmf-dist'
    required={name:[str(p.relative_to(tree)) for p in tree.rglob(name)] for name in ('luaotfload-main.lua','luatex85.sty')}
    assert all(required.values()),required
    envdir=ROOT/'tools/envs_v4/sphinx-doc__sphinx__412cebf1660c54966245a88269516e54d0a85c37'
    log=ROOT/'logs/sphinx_luatex_smoke.log'
    with tempfile.TemporaryDirectory(prefix='luatex-smoke-',dir=ROOT/'work') as td:
        work=Path(td)
        (work/'probe.tex').write_text(r'\documentclass{article}\usepackage{fontspec}\usepackage{luatex85}\begin{document}LuaTeX environment probe: $a^2+b^2=c^2$.\end{document}'+'\n')
        base=sandbox(work,'sphinx-doc/sphinx',envdir)
        base+=['--ro-bind',str(tree),'/opt/sphinx-texmf','--setenv','TEXMFHOME','/opt/sphinx-texmf','--setenv','TEXMFCACHE','/tmp/texmf-cache','--dir','/tmp/texmf-cache']
        cmd=['/usr/bin/lualatex','-interaction=nonstopmode','-halt-on-error','probe.tex']
        result=run_limited(base+cmd,work,log,timeout=120)
        result['pdf_created']=(work/'probe.pdf').exists()
    manifest=dict(package=PACKAGE,version=VERSION,package_sha256=digest,texmf_tree=str(tree),required_files=required,system_packages_modified=False,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),smoke=result)
    (ROOT/'records/sphinx_luatex_addon.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2),flush=True)
    if result['status']!='ok' or not result['pdf_created']:raise SystemExit(1)

if __name__=='__main__':main()
