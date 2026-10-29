"""Render tables directly from corrected, server-computed summaries."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'paper/generated'
def pct(x):return f'{100*x:.1f}'
def table(name,heads,rows,align):
    s='\\begin{tabular}{'+align+'}\n\\toprule\n'+' & '.join(heads)+' \\\\\n\\midrule\n'
    s+=''.join(' & '.join(r)+' \\\\\n' for r in rows)+'\\bottomrule\n\\end{tabular}\n'
    (OUT/name).write_text(s)
d=json.loads((ROOT/'results/sew_corrected_summary.json').read_text())
lookup={(r['model'],r['mode'],r['group'],r['edit'],r['method']):r for r in d['summary']}
rows=[]
for model,label in [('deepseek','DeepSeek'),('starcoder2','StarCoder2')]:
    for mode in ('official','no_global'):
        for edit,ename in [('original','Orig.'),('formatter','Format'),('dead_return','Return')]:
            n=lookup[model,mode,'positive',edit,'official'];c=lookup[model,mode,'positive',edit,'matched']
            nn=lookup[model,mode,'negative',edit,'official'];cn=lookup[model,mode,'negative',edit,'matched']
            rows.append([label,mode.replace('_','-'),ename,pct(n['detected']/n['n']),pct(nn['detected']/nn['n']),
                         pct(c['detected']/c['n']),pct(c['joint_count']/c['n']),pct(cn['detected']/cn['n'])])
table('sew_calibrated.tex',['Model','Address','Edit','TPR$_n$','FPR$_n$','TPR$_c$','Joint$_c$','FPR$_c$'],rows,'lllrrrrr')
table('sew.tex',['Model','Address','Edit','TPR$_n$','FPR$_n$','TPR$_c$','Joint$_c$','FPR$_c$'],rows,'lllrrrrr')
r=json.loads((ROOT/'results/recovery_summary.json').read_text())
lookup={(x['model'],x['group'],x['edit'],x['method']):x for x in r['summary']}
rows=[]
for model,label in [('deepseek','DeepSeek'),('starcoder2','StarCoder2')]:
    for edit,ename in [('original','Original'),('formatter','Format'),('dead_return','Return')]:
        for method,mname in [('envelope_p','SEW score'),('envelope_scan1','Radius-1 search')]:
            p=lookup[model,'positive',edit,method];n=lookup[model,'negative',edit,method]
            rows.append([label,ename,mname,str(p['detected']),str(p['joint_count']),str(n['detected'])])
table('recovery_development.tex',['Source','Edit','Detector','Detected','Joint','False alarms'],rows,'lllrrr')
rows=[]
for model,label in [('deepseek','DeepSeek'),('starcoder2','StarCoder2')]:
    for edit,ename in [('formatter','Format'),('dead_return','Return')]:
        for method,mname in [('frozen_scan1','Original only'),('matched_scan1','Edit matched'),('envelope_scan1','Envelope')]:
            p=lookup[model,'positive',edit,method];n=lookup[model,'negative',edit,method]
            rows.append([label,ename,mname,pct(p['detected']/p['n']),pct(n['detected']/n['n']),pct(p['joint_count']/p['n'])])
table('calibration_transfer.tex',['Source','Edit','Calibration','TPR','FPR','Joint'],rows,'lllrrr')
for c in r['contrasts']:
    if c['edit']=='dead_return' and c['method']=='envelope_scan1':print(c)
print('TABLES_WRITTEN')
