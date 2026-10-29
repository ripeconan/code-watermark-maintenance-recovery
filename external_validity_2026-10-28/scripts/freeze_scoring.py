"""Record immutable sample/algorithm provenance before first new scoring."""
import datetime,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OLD=Path('/home/icdm/crosslingual-codewatermark/maintenance_upgrade_20261028')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    manifest=ROOT/'records/scoring_freeze.json'
    if manifest.exists():
        old=json.loads(manifest.read_text())
        for path,digest in old['files'].items():assert sha(ROOT/path)==digest,('frozen input changed',path)
        print('FREEZE_VERIFIED',old['created_utc']);return
    assert not (ROOT/'results/temporal_scores.jsonl').exists(),'outcomes already exist before freeze'
    acquisition=json.loads((ROOT/'records/acquisition_summary.json').read_text())
    assert len(acquisition)==6 and all(r.get('complete') for r in acquisition)
    for name in ('evaluate_upgrade.py','replay_pilot.py','structured_candidates.py','fine_replay.py','analyze_upgrade.py'):
        assert sha(ROOT/'scripts'/name)==sha(OLD/'scripts'/name),name
    assert sha(ROOT/'records/development_dictionary.json')==sha(OLD/'records/development_dictionary.json')
    previous=json.loads((OLD/'results/upgrade_summary.json').read_text())
    (ROOT/'records/external_thresholds.json').write_text(json.dumps(previous['thresholds'],indent=2))
    files=[ROOT/'PROTOCOL.txt',ROOT/'CALIBRATION_MISSINGNESS_RULE.txt']
    files+=list((ROOT/'scripts').glob('*.py'))
    files+=list((ROOT/'records').glob('*.json'))
    files+=list((ROOT/'data/pairs').glob('*.gz'))
    data=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),previous_root=str(OLD),previous_scores_sha256=sha(OLD/'results/project_local_scores.jsonl'),files={str(p.relative_to(ROOT)):sha(p) for p in sorted(files)},planned_transitions=sum(sum(r['selected'].values()) for r in acquisition),planned_score_records=sum(sum(r['selected'].values())*3 for r in acquisition),planned_functional_transitions=sum(r['functional_transitions'] for r in acquisition),internal_prospective_record=True,externally_registered=False)
    manifest.write_text(json.dumps(data,indent=2))
    print('SCORING_FROZEN',data['planned_score_records'],data['created_utc'],flush=True)

if __name__=='__main__':main()
