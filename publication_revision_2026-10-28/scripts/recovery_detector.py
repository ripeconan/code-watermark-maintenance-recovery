"""Single-method detector API for fixed SEW embeddings.

No original program or edit label is accepted. A threshold is calibrated for
this method and population separately; min_p is a score, not a calibrated p.
"""
import argparse,json,math,time
from collections import defaultdict
from pathlib import Path
from recovery_probe import contexts,grade_score,init
from structural_recovery import syntax_candidates


def detect_recovery(code,language,key,method='syntax',threshold=None,deltas=None):
    from sew.sites.discovery import discover
    start=time.perf_counter();tree,_,recs=discover(code,language)
    if not recs:
        return dict(score=None,min_p=1.,grades=0,candidates=0,detected=False,reason='insufficient_evidence',seconds=time.perf_counter()-start)
    observed=tuple(map(int,recs[0].sid[-1][4:].split('.')));grades=defaultdict(list)
    for r in recs:grades[r.sid[:-1]].append(r.value)
    if method=='official':cs={observed}
    elif method=='syntax':cs=syntax_candidates(tree,observed,language)
    elif method=='delta_dictionary':
        if deltas is None:raise ValueError('validation-derived delta dictionary required')
        cs={observed}
        for delta in deltas:
            c=tuple(a-b for a,b in zip(observed,delta))
            if min(c)>=0:cs.add(c)
    elif method.startswith('l1_'):cs=set(contexts(observed,int(method[3:])))
    elif method=='nearest_budget':
        budget=len(syntax_candidates(tree,observed,language))
        ordered=sorted(contexts(observed,3),key=lambda c:(sum(abs(a-b) for a,b in zip(c,observed)),c))
        cs=set(ordered[:budget])
    else:raise ValueError(method)
    minp=min(grade_score(grades,c,key,language) for c in cs)
    eligible=len(grades)>=5;score=-minp if eligible else None
    decision=bool(eligible and threshold is not None and score>threshold)
    return dict(score=score,min_p=minp,grades=len(grades),candidates=len(cs),detected=decision,
                reason=('insufficient_evidence' if not eligible else ('uncalibrated' if threshold is None else 'thresholded')),
                seconds=time.perf_counter()-start)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('file');ap.add_argument('--language',required=True,choices=['python','java','cpp'])
    ap.add_argument('--vendor',required=True);ap.add_argument('--key-hex',required=True)
    ap.add_argument('--method',default='syntax',choices=['official','syntax','nearest_budget','l1_1','l1_2','l1_3','l1_4','delta_dictionary'])
    ap.add_argument('--dictionary',help='JSON with language-indexed deltas learned only from calibration negatives')
    ap.add_argument('--threshold',type=float);a=ap.parse_args();init(a.vendor)
    deltas=json.loads(Path(a.dictionary).read_text())['deltas'][a.language] if a.dictionary else None
    print(json.dumps(detect_recovery(Path(a.file).read_text(encoding='utf8'),a.language,bytes.fromhex(a.key_hex),a.method,a.threshold,deltas),indent=2))


if __name__=='__main__':main()
