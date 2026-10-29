"""Generate manuscript tables/figure directly from frozen result files."""
import json,collections
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'paper/generated';OUT.mkdir(exist_ok=True)
def read(name):return json.loads((ROOT/'results'/name).read_text())
def table(name,spec,header,rows):
    text='\\begin{tabular}{'+spec+'}\n\\toprule\n'+header+' \\\\\n\\midrule\n'+'\n'.join(' & '.join(map(str,r))+' \\\\' for r in rows)+'\n\\bottomrule\n\\end{tabular}\n'
    (OUT/name).write_text(text,encoding='utf8')
names={'mahmoud/boltons':'boltons','google/gson':'Gson','fmtlib/fmt':'fmt','pallets/itsdangerous':'itsdangerous','jhy/jsoup':'jsoup','gabime/spdlog':'spdlog','pallets/click':'Click','junit-team/junit4':'JUnit4','nlohmann/json':'json',
       'apache/commons-collections':'Collections','apache/commons-lang':'Lang','networkx/networkx':'NetworkX','sympy/sympy':'SymPy'}
exp=read('exposure_summary.json')
order={'development':0,'calibration':1,'test':2}
table('maintenance_exposure.tex','llrrrr',r'Project & Role & Sampled & Both parse & Changed & Covered',
 [[names[x['repo']],x['split'],x['sampled'],x['both_parse'],x['context_changed'],x['syntax_covers_changed']] for x in sorted(exp,key=lambda x:(x['language'],order[x['split']]))])
v1=read('upgrade_summary.json');v2=read('project_local_summary.json')
methods=['official','syntax','structured64','nearest64','dictionary64','dictionary_pairs64']
labels=['Official','Single subtree','Struct64','Nearest64','Dict64','DictPair64']
rows=[]
for m,label in zip(methods,labels):
    row=[label]
    for lang in ('java','python'):
        d={x['group']:x for x in v1['summary'] if x['method']==m and x['language']==lang and x['alpha']==.05}
        row+=[str(d['positive_after']['usable_detected'])+'/240',str(d['negative_after']['detected'])+'/240']
    rows.append(row)
table('maintenance_external.tex','lrrrr',r'Method & Java detected & Java alarms & Python detected & Python alarms',rows)
projects=list(v2['flow']);repos=[x['repo'] for x in projects]
table('maintenance_local_flow.tex','lrrrrrr',r'Project & Cal. & Test & Embed OK & Clean & Conflict & Error',
 [[names[x['repo']],x['calibration_files'],x['test_files'],x['embedding'].get('ok',0),x['replay'].get('clean',0),x['replay'].get('conflict',0),x['errors']] for x in projects])
def result(repo,method,mode='local_paired',alpha=.05):return next(x for x in v2['summary'] if (x['repo'],x['method'],x['mode'],x['alpha'])==(repo,method,mode,alpha))
table('maintenance_local_comparison.tex','lrrrrrr',r'Project & Official & Single & Struct64 & Nearest64 & Dict64 & DictPair64',
 [[names[p]]+[str((x:=result(p,m))['positive_after'])+'/'+str(x['negative_any']) for m in methods] for p in repos])
table('maintenance_local_calibration.tex','lrrrrrr',r'Project & Ext. D & Ext. A & Orig. D & Orig. A & Pair D & Pair A',
 [[names[p]]+[v for mode in ('external','local_original','local_paired') for v in (result(p,'structured64',mode)['positive_after'],result(p,'structured64',mode)['negative_any'])] for p in repos])
table('maintenance_local_intervals.tex','lrrr',r'Project & Difference (pp) & Lower & Upper',
 [[names[x['repo']],f"{100*x['mean']:.2f}",f"{100*x['ci95'][0]:.2f}",f"{100*x['ci95'][1]:.2f}"] for x in v2['paired_intervals'] if x['comparison']=='structured64-minus-syntax' and x['metric']=='positive_after'])
table('maintenance_local_all.tex','llrrrrrrrrr',r'Project & Mode & Off. & Single & S64 & S128 & N64 & N128 & R4 & D64 & DP64',
 [[names[p],mode.replace('local_','')] + [str((x:=result(p,m,mode))['positive_after'])+'/'+str(x['negative_any']) for m in ('official','syntax','structured64','structured128','nearest64','nearest128','l1_4','dictionary64','dictionary_pairs64')] for p in repos for mode in ('external','local_original','local_paired')])
plt.rcParams.update({'font.size':10,'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
fig,axs=plt.subplots(1,2,figsize=(8.4,3.6),layout='constrained');x=np.arange(4);width=.35
for i,(mode,label,color) in enumerate([('external','External negatives','#b2bac4'),('local_paired','Project-local pairs','#2e6390')]):
    y=[100*result(p,'structured64',mode)['negative_any']/240 for p in repos]
    axs[0].bar(x+(i-.5)*width,y,width,label=label,color=color)
axs[0].axhline(5,color='#9c4141',ls='--',lw=1,label='5% target')
axs[0].set_ylabel('Either-version negative alarms (%)');axs[0].set_ylim(0,50);axs[0].set_title('(a) Struct64: calibration population')
for j,(m,label,marker) in enumerate(zip(methods[:4],labels[:4],['o','s','^','D'])):
    y=[100*result(p,m)['positive_after']/240 for p in repos]
    axs[1].plot(x+(j-1.5)*.09,y,marker=marker,ls='',ms=5,label=label)
axs[1].set_ylabel('Post-maintenance detection (%)');axs[1].set_ylim(45,85);axs[1].set_title('(b) Project-local paired thresholds')
for ax in axs:
    ax.set_xticks(x,[names[p] for p in repos]);ax.tick_params(axis='x',labelsize=9);ax.legend(fontsize=9,frameon=False);ax.grid(axis='y',alpha=.2)
fig.savefig(OUT/'maintenance_calibration.pdf');fig.savefig(OUT/'maintenance_calibration.png',dpi=180);plt.close(fig)
timing=[json.loads(s) for s in (ROOT/'results/project_method_timing.jsonl').read_text().splitlines()]
scored={(r['id'],r['key']):r for s in (ROOT/'results/project_local_scores.jsonl').read_text().splitlines() if (r:=json.loads(s))}
for r in timing:
    if 'score' in r:
        expected=scored[r['id'],15485863].get('group_scores',{}).get('negative_after',{}).get('scores',{}).get(r['method'])
        if expected is not None:assert abs(r['score']-expected)<1e-12,(r['id'],r['method'])
tr=[]
for p in repos:
    rr=[r for r in timing if r['repo']==p and r.get('eligible')]
    n=len({r['id'] for r in rr});row=[names[p],n]
    for m in ('official','syntax','structured64','nearest64','dictionary64','dictionary_pairs64','l1_4'):
        row.append(f"{1000*np.median([r['seconds'] for r in rr if r['method']==m]):.2f}")
    tr.append(row)
table('maintenance_timing.tex','lrrrrrrrr',r'Project & $n$ & Off. & Single & S64 & N64 & D64 & DP64 & R4',tr)
table('maintenance_local_10percent.tex','lrrrrrr',r'Project & Official & Single & Struct64 & Nearest64 & Dict64 & DictPair64',
 [[names[p]]+[str((x:=result(p,m,alpha=.10))['positive_after'])+'/'+str(x['negative_any']) for m in methods] for p in repos])
print('Generated maintenance tables and figure from',v1['records'],'and',v2['records'],'records')

rocfile=ROOT/'results/project_diagnostic_roc.json'
if rocfile.exists():
    roc=json.loads(rocfile.read_text())['summary']
    table('maintenance_diagnostic_roc.tex','lrrrrrr',r'Project & Official & Single & Struct64 & Nearest64 & Dict64 & DictPair64',
      [[names[p]]+[f"{100*next(x['mean_sensitivity'] for x in roc if x['repo']==p and x['method']==m):.2f}" for m in methods] for p in repos])
    intervals=v2['paired_intervals']
    def ci(p,m,metric):
        x=next(x for x in intervals if x['repo']==p and x['comparison']=='structured64-minus-'+m and x['metric']==metric)
        return f"{100*x['mean']:+.2f} [{100*x['ci95'][0]:+.2f}, {100*x['ci95'][1]:+.2f}]"
    table('maintenance_all_intervals.tex','llrr',r'Project & Comparator & Detection difference [95\% CI] & Alarm difference [95\% CI]',
      [[names[p],label,ci(p,m,'positive_after'),ci(p,m,'negative_any')] for p in repos for m,label in zip(methods,labels) if m!='structured64'])
boundaryfile=ROOT/'results/candidate_boundary_summary.json'
if boundaryfile.exists():
    bs=json.loads(boundaryfile.read_text())['summary'];rows=[]
    for lang in ('python','java','cpp'):
        for edit in ('nested_helper','two_helpers'):
            vals=[]
            for m in ('syntax','structured64','structured128','structured1000000000','nearest64','dictionary_pairs64'):
                x=next(x for x in bs if (x['language'],x['edit'],x['method'])==(lang,edit,m))
                vals.append(str(x['covered'])+' ('+f"{x['median_candidates']:g}"+')')
            rows.append([{'python':'Python','java':'Java','cpp':'C++'}[lang],edit.replace('_',' ')]+vals)
    table('maintenance_boundary_coverage.tex','llrrrrrr',r'Language & Edit & Single & S64 & S128 & Uncapped & N64 & DP64',rows)
sourcefile=ROOT/'results/calibration_source_control.json'
if sourcefile.exists():
    cs=json.loads(sourcefile.read_text())['summary']
    pairs=sorted({(r['target'],r['source']) for r in cs})
    table('maintenance_source_control.tex','llrrrrrr',r'Test project & Calibration project & Official & Single & S64 & N64 & D64 & DP64',
      [[names[t],names[s]]+[str((x:=next(r for r in cs if (r['target'],r['source'],r['method'])==(t,s,m)))['positive_after'])+'/'+str(x['negative_any']) for m in methods] for t,s in pairs])
ff=ROOT/'results/functional_summary.json'
if ff.exists():
    fs=json.loads(ff.read_text())['summary']
    if all('missing_original_suite' in x for x in fs):
        table('maintenance_functional_flow.tex','lrrrrr',r'Project & Original pair & All four & No suite & Conflict & Marked failure',
          [[names[x['repo']],x['original_pair_pass'],x['all_four_pass'],x['missing_original_suite'],x['replay_conflict'],x['marked_failure_with_original_pass']] for x in fs])
        table('maintenance_functional_joint.tex','lrrrrrr',r'Project & Official & Single & Struct64 & Nearest64 & Dict64 & DictPair64',
          [[names[x['repo']]]+[x['joint'][m] for m in methods] for x in fs])
        table('maintenance_functional_detect.tex','lrrrrrr',r'Project & Official & Single & Struct64 & Nearest64 & Dict64 & DictPair64',
          [[names[x['repo']]]+[x['detection'][m] for m in methods] for x in fs])
