"""Compare relocated frozen algorithms with existing successful observations."""
import gzip,hashlib,json
from pathlib import Path
from evaluate_temporal import isolated,ROOT
OLD=Path('/home/icdm/crosslingual-codewatermark/maintenance_upgrade_20261028')

def strip_runtime(obj):
    if isinstance(obj,dict):return {k:strip_runtime(v) for k,v in obj.items() if k not in ('seconds','elapsed','elapsed_seconds')}
    if isinstance(obj,list):return [strip_runtime(v) for v in obj]
    return obj

def main():
    previous=[json.loads(s) for s in (OLD/'results/project_local_scores.jsonl').read_text().splitlines() if s]
    raw={r['id']:r for p in (OLD/'data/project_calibration').glob('*.json.gz') if '.frame.' not in p.name for r in json.loads(gzip.decompress(p.read_bytes()))}
    dictionary=json.loads((ROOT/'records/development_dictionary.json').read_text())
    checks=[]
    for language in ('python','java'):
        for split in ('calibration','test'):
            candidates=sorted((r for r in previous if r['language']==language and r['split']==split and 'error' not in r and (split=='calibration' or r.get('merge_status')=='clean')),key=lambda r:(r['id'],r['key']))
            old=candidates[0];new=isolated(dict(row=raw[old['id']],key=old['key'],dictionary=dictionary))
            fields=['group_scores']+(['embedding','replay_detail','merge_status','marked_context_changed'] if split=='test' else [])
            same={field:strip_runtime(old.get(field))==strip_runtime(new.get(field)) for field in fields}
            if split=='test':same['code_sha256']=old['code_sha256']=={g:hashlib.sha256(c.encode()).hexdigest() for g,c in new.get('codes',{}).items()}
            checks.append(dict(id=old['id'],key=old['key'],language=language,split=split,checks=same,error=new.get('error')))
    result=dict(passed=all(all(r['checks'].values()) and not r['error'] for r in checks),checks=checks)
    (ROOT/'records/parity_check.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
