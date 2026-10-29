"""Export the completed server evidence only after every planned job is present."""
import json,platform,subprocess,tarfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    from test_project_local import collect
    paths=['project_local_tests.jsonl','project_local_tests_sympydeps.jsonl','project_local_tests_javatransport.jsonl','project_local_tests_javaprovider.jsonl','project_local_tests_javabatch.jsonl']
    canonical={}
    for name in paths:
        p=ROOT/'results'/name
        if p.exists():
            for s in p.read_text().splitlines():
                r=json.loads(s);canonical[r['job_id']]=r
    planned={r['job_id'] for r in collect()}
    assert planned==set(canonical),(len(planned),len(canonical),len(planned-set(canonical)))
    assert len(planned)==240
    subprocess.run([sys.executable,str(ROOT/'scripts/analyze_functional.py')],check=True)
    info=dict(planned_jobs=len(planned),recorded_jobs=len(canonical),complete=True,python=sys.version,platform=platform.platform())
    (ROOT/'records/completion_audit.json').write_text(json.dumps(info,indent=2))
    files=set()
    for folder in ('results','logs','data/upgrade_codes','data/project_local_codes','data/licenses'):
        files.update(p for p in (ROOT/folder).rglob('*') if p.is_file())
    for p in (ROOT/'records').rglob('*'):
        if p.is_file() and p.suffix in ('.txt','.json','.jsonl') and 'pdf_review' not in p.parts:files.add(p)
    for p in (ROOT/'scripts').glob('run_java*.sh'):files.add(p)
    dest=ROOT/'records/completed_server_evidence.tar.gz'
    with tarfile.open(dest,'w:gz') as tf:
        for p in sorted(files):
            name=p.relative_to(ROOT).as_posix()
            if name=='records/notice_files.json':name='records/notice_files_server.json'
            tf.add(p,arcname=name,recursive=False)
    print('COMPLETED_EXPORT',dest, dest.stat().st_size)
if __name__=='__main__':main()
