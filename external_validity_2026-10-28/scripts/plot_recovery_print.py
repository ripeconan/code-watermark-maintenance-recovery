"""Publication figures from server-derived held-out detection summaries."""
import json,hashlib
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
path=ROOT.parent/'publication_revision_2026-10-28/results/confirmation_summary.json'
d=json.loads(path.read_text());assert d['missing_functional']==0
lookup={(r['language'],r['method'],r['group'],r['edit']):r for r in d['summary'] if r['regime']=='envelope' and r['alpha']==.05}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'pdf.fonttype':42,'ps.fonttype':42})
colors={'official':'0.5','delta_dictionary':'0.15','nearest_budget':'0.4','l1_4':'0.6','syntax':'0.0'}
markers={'official':'o','delta_dictionary':'s','nearest_budget':'^','l1_4':'D','syntax':'P'}
labels={'official':'Official score','delta_dictionary':'Learned edit dictionary','nearest_budget':'Equal-budget search','l1_4':'Radius-4 search','syntax':'Syntax-derived search'}
fig,axes=plt.subplots(3,3,figsize=(7.3,6.6),sharey=True)
for col,lang in enumerate(('python','java','cpp')):
    for row,edit in enumerate(('helper','formatter_helper','helper_loop')):
        ax=axes[row,col]
        for method in colors:
            r=lookup[lang,method,'positive',edit];v=r['detection'];x=r['candidates_mean'];y=100*v['mean']
            ax.errorbar(x,y,yerr=[[y-100*v['lo']],[100*v['hi']-y]],fmt=markers[method],ms=5,color=colors[method],capsize=2,label=labels[method])
            neg=lookup[lang,method,'negative',edit]
            offset={'official':(3,4),'delta_dictionary':(4,-11),'nearest_budget':(3,3),'l1_4':(-42,-11),'syntax':(4,4)}[method]
            if row==2 and method=='official':offset=(0,-12)
            if row==2 and method=='delta_dictionary':offset=(4,4)
            ax.annotate(f"{100*neg['detected']/neg['n']:.1f}%",(x,y),xytext=offset,textcoords='offset points',fontsize=7,color='0.15')
        ax.set_xscale('log');ax.set_xlim(.7,500);ax.set_ylim(-3,108);ax.set_xticks([1,10,100]);ax.set_xticklabels(['1','10','100'])
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2)
        if row==0:ax.set_title({'python':'Python','java':'Java','cpp':'C++'}[lang],weight='bold')
        if row==2:ax.set_xlabel('Mean context candidates')
        if col==0:ax.set_ylabel(('Known helper','Formatting + helper','Unseen loop helper')[row]+'\nDetection (%)')
handles,legend=axes[0,0].get_legend_handles_labels();fig.legend(handles,legend,loc='lower center',ncol=2,bbox_to_anchor=(.5,-.01),frameon=False)
fig.subplots_adjust(left=.1,right=.98,top=.94,bottom=.14,hspace=.22,wspace=.15)
dest=ROOT/'paper/generated';fig.savefig(dest/'recovery_budget.pdf',bbox_inches='tight');fig.savefig(dest/'recovery_budget.png',dpi=220,bbox_inches='tight')
plt.close(fig)
(ROOT/'records').mkdir(exist_ok=True)
(ROOT/'records/paper_figure_audit.json').write_text(json.dumps(dict(source=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),change='Same numeric inputs; grayscale and distinct marker shapes for print readability; main figure only'),indent=2))
print('GRAYSCALE_FIGURE_WRITTEN')
