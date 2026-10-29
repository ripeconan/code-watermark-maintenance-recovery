"""Evidence checks independent of manuscript tables."""
import gzip,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def h(data):return hashlib.sha256(data).hexdigest()

def main():
    freeze=json.loads((ROOT/'records/scoring_freeze.json').read_text())
    for rel,digest in freeze['files'].items():assert h((ROOT/rel).read_bytes())==digest,rel
    acquisitions=json.loads((ROOT/'records/acquisition_summary.json').read_text())
    raw=[];checks=[]
    for acquisition in acquisitions:
        slug=acquisition['repo'].replace('/','__')
        frame=json.loads(gzip.decompress((ROOT/'data/pairs'/f'{slug}.frame.json.gz').read_bytes()))
        rows=json.loads(gzip.decompress((ROOT/'data/pairs'/f'{slug}.json.gz').read_bytes()))
        raw+=rows
        assert len({r['sha'] for r in frame})==len(frame)
        assert len({(r['before_sha256'],r['after_sha256']) for r in frame})==len(frame)
        for row in rows:
            assert h(row['before'].encode())==row['before_sha256']
            assert h(row['after'].encode())==row['after_sha256']
        cal=[r for r in rows if r['split']=='calibration'];test=[r for r in rows if r['split']=='test']
        assert max(r['timestamp'] for r in cal)<min(r['timestamp'] for r in test)
        assert not {r['sha'] for r in cal}&{r['sha'] for r in test}
        functional=json.loads((ROOT/'records'/f'functional_{slug}.json').read_text())
        expected=sorted(test,key=lambda r:h(('external-functional-v1|'+r['id']).encode()))[:24]
        assert [r['id'] for r in functional]==[r['id'] for r in expected]
        checks.append(dict(repo=acquisition['repo'],strict_temporal_order=True,unique_commits=True,functional_preselection_matches=True,transitions=len(rows)))
    scorefile=ROOT/'results/temporal_scores.jsonl'
    rows=[json.loads(s) for s in scorefile.read_text().splitlines() if s]
    expected={(r['id'],key) for r in raw for key in (15485863,32452843,49979687)}
    assert {(r['id'],r['key']) for r in rows}==expected
    assert len(rows)==len(expected)==freeze['planned_score_records']
    hashes=0
    for row in rows:
        if row.get('codes_file'):
            codes=json.loads(gzip.decompress((ROOT/row['codes_file']).read_bytes()))
            assert {group:h(code.encode()) for group,code in codes.items()}==row['code_sha256']
            hashes+=len(codes)
    summary=json.loads((ROOT/'results/temporal_summary.json').read_text())
    for item in summary['summary']:
        assert 0<=item['positive_after']<=item['n']
        assert 0<=item['negative_any']<=item['negative_upper']<=item['n']
        planned=sum(r['repo']==item['repo'] and r['split']=='test' for r in raw)*3
        assert item['n']==planned
    result=dict(passed=True,records=len(rows),planned_transitions=len(raw),verified_code_hashes=hashes,scoring_results_sha256=h(scorefile.read_bytes()),project_checks=checks)
    (ROOT/'records/verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
