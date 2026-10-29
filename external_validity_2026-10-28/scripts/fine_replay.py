"""Conservative ancestor-coordinate textual merge, not an edit oracle detector."""
import difflib

def edits(base,branch):
    a,b=base.splitlines(keepends=True),branch.splitlines(keepends=True)
    offsets=[0]
    for line in a:offsets.append(offsets[-1]+len(line))
    out=[]
    for tag,i,j,k,l in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        if tag=='equal':continue
        old,new=''.join(a[i:j]),''.join(b[k:l]);offset=offsets[i]
        for kind,s,e,u,v in difflib.SequenceMatcher(None,old,new,autojunk=False).get_opcodes():
            if kind!='equal':out.append((offset+s,offset+e,new[u:v]))
    assert apply(base,out)==branch,'branch reconstruction failure'
    return out

def apply(base,operations):
    result=base
    for s,e,new in sorted(operations,key=lambda p:(p[0],p[1]),reverse=True):result=result[:s]+new+result[e:]
    return result

def overlap(a,b):
    x,y,_=a;u,v,_=b
    if x==y and u==v:return x==u
    if x==y:return u<x<v
    if u==v:return x<u<y
    return max(x,u)<min(y,v)

def merge(base,marked,revised):
    wm,dev=edits(base,marked),edits(base,revised);conflicts=[]
    for i,a in enumerate(wm):
        for j,b in enumerate(dev):
            if a!=b and overlap(a,b):conflicts.append((i,j))
    info=dict(watermark_edits=len(wm),developer_edits=len(dev),overlaps=len(conflicts),
        duplicate_edits=len(set(wm)&set(dev)),conflict_examples=conflicts[:8])
    if conflicts:return None,info
    return apply(base,set(wm)|set(dev)),info

def self_check():
    # Disjoint same-line changes should both survive; touching boundaries retain
    # insertions, while competing replacement/insertions must remain conflicts.
    assert merge('return a + b;\n','return a+b;\n','return a + c;\n')[0]=='return a+c;\n'
    assert merge('abc','aXc','aYc')[0] is None
    assert merge('ab','aXb','aYb')[0] is None
    assert merge('abc','aXbc','aYc')[0]=='aXYc'
    assert merge('abc','ac','ac')[0]=='ac'
    assert merge('abc','abc','XYZ')[0]=='XYZ'
    assert merge('αβ\n','α β\n','αβ!\n')[0]=='α β!\n'

if __name__=='__main__':
    self_check();print('Fine-replay boundary and conflict checks passed.')
