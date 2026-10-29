"""Budgeted hypotheses from disjoint observed subtrees; no key or edit input."""
import itertools,collections

def nodes_and_vectors(tree,language):
    from sew.sites.ctx import FUNC,PARAMS,PARAM_ITEM,LOOP,RET
    stack=[(tree.root_node,False)];counts={};nodes=[]
    while stack:
        n,ready=stack.pop()
        if not ready:
            stack.append((n,True));stack.extend((c,False) for c in n.children);continue
        v=[0,0,0,0]
        if n.type in FUNC[language]:v[0]=1
        elif n.type in PARAMS[language]:v[1]=sum(c.type in PARAM_ITEM[language] for c in n.children)
        elif n.type in LOOP[language]:v[2]=1
        elif n.type in RET[language]:v[3]=1
        for c in n.children:
            w=counts.pop(c.id)
            for j in range(4):v[j]+=w[j]
        counts[n.id]=v
        if n.type in FUNC[language]|LOOP[language]|{'if_statement'} and any(v):nodes.append((n.start_byte,n.end_byte,tuple(v)))
    return nodes

def structured(tree,observed,language,budget=64):
    observed=tuple(observed);nodes=nodes_and_vectors(tree,language)
    def subtract(v):
        c=tuple(a-b for a,b in zip(observed,v));return c if min(c)>=0 else None
    singles={c for _,_,v in nodes if (c:=subtract(v)) is not None}
    pairs=set()
    for a,b in itertools.combinations(nodes,2):
        if a[1]>b[0] and b[1]>a[0]:continue
        c=subtract(tuple(x+y for x,y in zip(a[2],b[2])))
        if c is not None:pairs.add(c)
    order=lambda c:(sum(abs(a-b) for a,b in zip(observed,c)),c)
    axial=[]
    for j in range(4):
        for step in (-1,1):
            c=list(observed);c[j]+=step
            if min(c)>=0:axial.append(tuple(c))
    chosen=[];seen=set()
    def add(c):
        if c not in seen and len(chosen)<budget:chosen.append(c);seen.add(c)
    add(observed)
    for c in sorted(axial,key=order):add(c)
    for a,b in itertools.zip_longest(sorted(singles,key=order),sorted(pairs,key=order)):
        if a is not None:add(a)
        if b is not None:add(b)
        if len(chosen)>=budget:break
    return set(chosen),dict(single_pool=len(singles),pair_pool=len(pairs),structural_nodes=len(nodes))

def nearest(observed,budget):
    from recovery_probe import contexts
    r=0;cs=[]
    while len(cs)<budget:
        r+=1;cs=contexts(observed,r)
    return set(sorted(cs,key=lambda c:(sum(abs(x-y) for x,y in zip(c,observed)),c))[:budget])

def dictionary(observed,entries,budget=64,combinations=False):
    frequencies={tuple(e['delta']):e['count'] for e in entries};freq=dict(frequencies)
    ranked={d:(1,-n,sum(map(abs,d)),d) for d,n in freq.items()}
    if combinations:
        for a,b in itertools.combinations_with_replacement(freq,2):
            d=tuple(x+y for x,y in zip(a,b));rank=(2,-freq[a]*freq[b],sum(map(abs,d)),d)
            if d not in ranked or rank<ranked[d]:ranked[d]=rank
    chosen={tuple(observed)}
    for d in sorted(ranked,key=ranked.get):
        c=tuple(x-y for x,y in zip(observed,d))
        if min(c)>=0:chosen.add(c)
        if len(chosen)>=budget:break
    return chosen

def fit_dictionary(exposure):
    by_language=collections.defaultdict(collections.Counter);seen=set()
    for r in exposure:
        if r['split']!='development' or 'delta' not in r:continue
        d=tuple(r['delta']);unit=(r['repo'],r['sha'],d)
        if unit in seen:continue
        seen.add(unit);by_language[r['language']][d]+=1
    return {lang:[dict(delta=d,count=n) for d,n in sorted(counts.items(),key=lambda x:(-x[1],sum(map(abs,x[0])),x[0]))] for lang,counts in by_language.items()}
