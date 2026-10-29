"""Strong control: learn count-change signatures from validation negatives only.

Added after initial detection results as a stronger comparator, not a newly
preregistered primary method. Code, embedding, edits and functional inputs stay
identical. The helper-loop challenge is excluded from the learned dictionary.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import concurrent.futures,hashlib,json,time
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def init(vendor,dictionaries):
    import recovery_probe
    recovery_probe.init(vendor)
    global discover,grade_score,DICTIONARIES
    from sew.sites.discovery import discover
    from recovery_probe import grade_score
    DICTIONARIES=dictionaries


def work(row):
    lang=row['language'];key=hashlib.sha256(('confirmation20261028|'+str(row['key'])).encode()).digest()
    for group in row['groups'].values():
        for v in group['variants'].values():
            tree,_,recs=discover(v['code'],lang);d=v['detection']
            if not recs:d['scores']['delta_dictionary']=1.;d['candidates']['delta_dictionary']=0;continue
            observed=tuple(map(int,recs[0].sid[-1][4:].split('.')))
            candidates={observed}
            for delta in DICTIONARIES[lang]:
                c=tuple(a-b for a,b in zip(observed,delta))
                if min(c)>=0:candidates.add(c)
            grades=defaultdict(list)
            for r in recs:grades[r.sid[:-1]].append(r.value)
            d['scores']['delta_dictionary']=min(grade_score(grades,c,key,lang) for c in candidates)
            d['candidates']['delta_dictionary']=len(candidates)
    return row


def main():
    rows=[json.loads(s) for s in (ROOT/'results/confirmation.jsonl').read_text().split('\n') if s]
    dictionaries={l:{(0,0,0,0)} for l in ('python','java','cpp')}
    for r in rows:
        if r['split']!='valid':continue
        vs=r['groups']['negative']['variants'];original=vs['original']['detection']['context']
        if original is None:continue
        for edit in ('original','formatter','helper','formatter_helper'):
            ctx=vs.get(edit,{}).get('detection',{}).get('context')
            if ctx is not None:dictionaries[r['language']].add(tuple(b-a for a,b in zip(original,ctx)))
    dictionaries={l:sorted(v) for l,v in dictionaries.items()}
    (ROOT/'records/context_delta_dictionary.json').write_text(json.dumps(dict(training='valid negatives only; helper_loop excluded',deltas=dictionaries),indent=2))
    print('DICTIONARIES',dictionaries,flush=True)
    vendor=json.loads((ROOT/'records/tool_paths.json').read_text())['vendor'];start=time.time()
    with (ROOT/'results/confirmation_augmented.jsonl').open('w') as f,concurrent.futures.ProcessPoolExecutor(max_workers=2,initializer=init,initargs=(vendor,dictionaries)) as ex:
        for i,r in enumerate(ex.map(work,rows,chunksize=2),1):
            f.write(json.dumps(r,ensure_ascii=False)+'\n')
            if i%250==0:f.flush();print('AUGMENT',i,len(rows),round(time.time()-start,1),flush=True)
    print('AUGMENT_DONE',len(rows),round(time.time()-start,1),flush=True)


if __name__=='__main__':main()
