"""Recover missing null measurements separately from failed positive work units."""
import argparse,gzip,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--worker',action='store_true');a=ap.parse_args()
    if a.worker:
        from evaluate_upgrade import init,score
        init();j=json.load(sys.stdin);key=hashlib.sha256(('confirmation20261028|'+str(j['key'])).encode()).digest()
        print(json.dumps(score(j['code'],j['language'],key,j['dictionary'])));return
    raw={}
    for folder in ('data/pairs','data/project_calibration'):
        for p in (ROOT/folder).glob('*.json.gz'):
            if '.frame.' not in p.name:raw.update({r['id']:r for r in json.loads(gzip.decompress(p.read_bytes()))})
    learned=json.loads((ROOT/'records/development_dictionary.json').read_text());out=[]
    for cohort,filename in [('v1','upgrade_scores.jsonl'),('v2','project_local_scores.jsonl')]:
        for line in (ROOT/'results'/filename).read_text().splitlines():
            r=json.loads(line)
            if 'error' not in r:continue
            row=raw[r['id']]
            for group,src in [('negative_before','before'),('negative_after','after')]:
                for repeat in (0,1):
                    j=dict(code=row[src],language=r['language'],key=r['key'],dictionary=learned.get(r['language'],[]))
                    p=subprocess.run([sys.executable,__file__,'--worker'],input=json.dumps(j),capture_output=True,text=True,timeout=120)
                    result=dict(id=r['id'],key=r['key'],cohort=cohort,repo=r['repo'],group=group,repeat=repeat,original_error=r['error'])
                    if p.returncode:result['audit_error']=str(p.returncode)+p.stderr[-500:]
                    else:result['measurement']=json.loads(p.stdout)
                    out.append(result);print('NULL_AUDIT',cohort,r['repo'],group,repeat,p.returncode,flush=True)
    (ROOT/'results/failed_negative_audit.json').write_text(json.dumps(out,indent=2))
if __name__=='__main__':main()
