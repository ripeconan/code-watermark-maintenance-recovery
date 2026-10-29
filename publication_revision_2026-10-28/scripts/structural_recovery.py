"""Detector-only hypotheses from suspect syntax; no original source or edit log."""
import itertools,time
from collections import defaultdict
from recovery_probe import contexts,grade_score


def subtree_counts(root,language):
    from sew.sites.ctx import FUNC,PARAMS,PARAM_ITEM,LOOP,RET
    counts=[0,0,0,0];stack=[root]
    while stack:
        n=stack.pop();stack.extend(n.children)
        if n.type in FUNC[language]:counts[0]+=1
        elif n.type in PARAMS[language]:counts[1]+=sum(c.type in PARAM_ITEM[language] for c in n.children)
        elif n.type in LOOP[language]:counts[2]+=1
        elif n.type in RET[language]:counts[3]+=1
    return tuple(counts)


def syntax_candidates_reference(tree,observed,language):
    from sew.sites.ctx import FUNC,LOOP
    candidates={observed};stack=[tree.root_node]
    while stack:
        n=stack.pop();stack.extend(n.children)
        if n.type not in FUNC[language]|LOOP[language]|{'if_statement'}:continue
        delta=subtree_counts(n,language)
        candidate=tuple(a-b for a,b in zip(observed,delta))
        if any(delta) and min(candidate)>=0:candidates.add(candidate)
    return candidates


def syntax_candidates(tree,observed,language):
    """The same candidate set, with subtree counts computed in one postorder pass."""
    from sew.sites.ctx import FUNC,PARAMS,PARAM_ITEM,LOOP,RET
    candidates={observed};stack=[(tree.root_node,False)];counts={}
    while stack:
        node,ready=stack.pop()
        if not ready:
            stack.append((node,True));stack.extend((child,False) for child in node.children)
            continue
        value=[0,0,0,0]
        if node.type in FUNC[language]:value[0]=1
        elif node.type in PARAMS[language]:value[1]=sum(c.type in PARAM_ITEM[language] for c in node.children)
        elif node.type in LOOP[language]:value[2]=1
        elif node.type in RET[language]:value[3]=1
        for child in node.children:
            v=counts.pop(child.id)
            for j in range(4):value[j]+=v[j]
        counts[node.id]=value
        if node.type in FUNC[language]|LOOP[language]|{'if_statement'} and any(value):
            candidate=tuple(a-b for a,b in zip(observed,value))
            if min(candidate)>=0:candidates.add(candidate)
    return candidates


def score_code(code,language,key,oracle_ctx=None,max_radius=3):
    from sew.sites.discovery import discover
    from sew.detect import detect
    start=time.perf_counter();tree,_,recs=discover(code,language)
    official=detect(code,language,key)
    if not recs:
        return dict(official=official,context=None,candidates={},scores={},seconds=time.perf_counter()-start)
    observed=tuple(map(int,recs[0].sid[-1][4:].split('.')))
    grades=defaultdict(list)
    for r in recs:grades[r.sid[:-1]].append(r.value)
    sets={'official':{observed},'syntax':syntax_candidates(tree,observed,language)}
    for radius in range(1,max_radius+1):sets['l1_'+str(radius)]=set(contexts(observed,radius))
    # Equal candidate budget, deterministic distance ordering independent of key.
    candidates=sorted(contexts(observed,max(3,max_radius)),key=lambda c:(sum(abs(a-b) for a,b in zip(c,observed)),c))
    sets['nearest_budget']=set(candidates[:len(sets['syntax'])])
    if oracle_ctx is not None:sets['oracle']={tuple(oracle_ctx)}
    cache={c:grade_score(grades,c,key,language) for c in set.union(*sets.values())}
    assert abs(cache[observed]-official['p'])<1e-12
    scores={name:min(cache[c] for c in cs) for name,cs in sets.items()}
    return dict(official=official,context=list(observed),
                candidates={name:len(cs) for name,cs in sets.items()},scores=scores,
                syntax_candidates=[list(c) for c in sorted(sets['syntax'])],
                seconds=time.perf_counter()-start)
