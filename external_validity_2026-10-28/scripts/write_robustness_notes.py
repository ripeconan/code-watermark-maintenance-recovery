"""Write UTF-8 delivery notes without a Windows legacy-encoding pipe."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'robustness_revision_20261029'
def main():
    (ROOT/'README.txt').write_text('''当前审阅稿：2026-10-29 实质修订版
先读 FINAL_REPORT.txt，再读 paper/main.pdf（21页）和 paper/supplement.pdf（28页）。
本轮完成P0文献证据矩阵、P1校准样本选择敏感性、P2重放策略配对对照、P3主文和补充材料改写。新增分析使用既有数据，不构成新的独立确认队列。
新增证据及DeepSeek协作日志：robustness_revision_20261029/。
旧主文/补充源码和PDF：robustness_revision_20261029/paper_before_revision.zip。
旧交付说明：robustness_revision_20261029/delivery_before_revision/。
原检测/功能原始证据保持不变：detection_phase/、functional_phase/及exports/*phase*.zip。
Windows大小写映射见functional_phase/WINDOWS_PATH_MAP.json；忽略partial解压目录。

快速核验：python scripts/verify_robustness_delivery.py
更新新增图表：python scripts/revision_assets.py
复编：python scripts/build_paper.py
视觉检查：python scripts/render_paper_qa.py --version 一个尚未存在的目录名
已有最终图表可直接复编；不要为复编重新执行实验或覆盖冻结结果。
实验复现规则和服务器路径见 robustness_revision_20261029/REPRODUCE.txt。
当前为匿名审阅稿，未投稿或公开发布。真实作者信息及公开artifact位置仍见AUTHOR_FINALIZATION.txt。
''',encoding='utf-8')
    (ROOT/'STATUS.txt').write_text('''2026-10-29：本轮P0/P1/P2/P3实质修改及交付核验完成。
原六项目实验于2026-10-29 01:33北京时间结束。本轮P1与P2已在inner完成；没有待跑功能任务。
P2共135个行级clean输出全部与原字符重放字节相同，按冻结规则复用对应旧检测和全套测试；新增score/test任务为0。
当前主文21页、补充28页，编译无警告，49页均已视觉检查。
改稿记录、四轮真实DeepSeek Flash复核和结果核验在robustness_revision_20261029/。
未投稿，未公开发布；旧稿及原始数据完整保留。
''',encoding='utf-8')
    (ROOT/'FINAL_REPORT.txt').write_text('''论文实质修订交付说明（2026-10-29）

已完成此前达成的P0—P3方案。主文21页，补充28页，均通过编译和视觉检查。
主文：paper/main.pdf
补充：paper/supplement.pdf
标题：Code-Watermark Recovery under Maintenance: Search, Calibration, and Replay
仍以JSEP Empirical为候选定位；此次没有投稿或更换期刊。

P0：文献与贡献边界
逐节核对SEW、CREST、SynMark、Signature filtering，并纳入CodeMarkBench公开artifact的评价先例。SEW已测过上下文/grade存活，CREST已讨论校准迁移，检测侧增强和联合可靠性均有先例。正文据此改为具体操作条件的量化，不宣称发现去同步、新校准理论或首个联合评价。
交付：robustness_revision_20261029/P0_PRIMARY_SOURCE_MATRIX.txt；Related Work具体节/表对照；补充分母映射表。

P1：校准样本选择敏感性
在inner固定早期池抽20/40/80个转变，各5000个无放回子集；同一子集在三key和六方法共享；固定较晚687转变。先精确复现108阈值和12366主要判定，原4125条分数不改。
Struct64的六项目等权检测率中位数及[2.5%,97.5%]经验分位数：
20：62.24% [52.32%,67.43%]
40：66.50% [62.46%,67.68%]
80：66.91% [66.17%,67.64%]
全池：67.10%，确定性单点。
这是固定历史池内的样本选择敏感性，不是未来风险置信区间。缺失阴性导致无穷阈值的机制用逐项目/key超几何精确概率核对；观察频率最大偏差约1.37个MC标准误。全部预算、方法和逐key结果保留。
交付：p1_freeze.json、p1_parity.json、p1_results.json、p1_draws.npz和新图表。

P2：同一432次评估的重放策略对照
固定Git2.34.1和命令，对同一144转变/3key的归档输入比较字符重放与行级git merge-file。重导出核对431已到达状态和338旧child程序。33嵌入弃判、1评分前置错误保留。
398个成功嵌入且可达记录中：字符clean305；行clean135、conflict263。
135个共同clean程序全部字节相同，分数和功能测试按代码/commit/path/key/冻结配方身份复用；零新score/test任务。170个字符clean在行策略中冲突，93个两者均冲突。
共同432分母下，联合检出且原始/标记父子四版全通过：
Official：字符159，行73。
Single：字符181，行84。
Struct64：字符183（42.36%），行85（19.68%）。
Struct64减少的98次全部位于字符clean转行conflict集合。共同clean中两边都是93次四版通过、85次Struct64联合成功；这不是两次独立证据。
实质改进：把单个Checkstyle异常案例扩展为同队列的政策依赖量化。原字符结果不能直接代表普通Git工作流；行级冲突也不能说成水印损伤。没有不同clean程序，故不比较分歧clean重构的功能。
交付：p2_policy_freeze.json、p2_plan.json、p2_summary.json、p2_decisions.json及配对表。

P3：论证与交付
标题、摘要、引言/RQ、相关工作、讨论和结论统一为三条实证贡献：固定水印恢复的机制与对照；校准总体和有限样本选择的操作条件；重放可用性与完整测试联合产出的配对证据。新增分析明确标为看到原结果后局部冻结的稳健性研究，未冒称独立确认或外部预注册。
verify_robustness_delivery.py核对原输入哈希、抽样汇总、135个缓存测试身份、183/85/98配对结果，全部通过。主文和补充编译无警告，49页视觉检查无截断或重叠。

DeepSeek合作
本轮真实通过OpenCode调用deepseek/deepseek-flash四轮，输入哈希、原始回答及用量在robustness_revision_20261029/reviews/；模型身份复核在model_collaboration_audit.json。意见逐项核验，不把模型同意当作外审或创新证明。Git返回码、CREST、条件化比值等误判及双方修正均保留在REVIEW_DISPOSITION.txt，未改写原始回答。
最后一轮在明确限定的复核范围内未发现必须修改的事实、分母或统计错误，认为当前范围可交付；它没有逐行重读全部最终文件，不称为独立完整审计。

当前判断
本次提升是补充了会实质改变结论的证据，并明确方法增量与工作流条件。没有得到显著算法突破，也不将183变85包装成方法性能改善。不能据内部评审宣称超过JSEP平均论文水准或保证录用。当前交付的是可供作者审阅的完整研究稿，而非已投稿稿。
真实作者、单位、通讯邮箱、基金/利益冲突及公开数据代码位置，仍须按真实信息补齐。旧稿存paper_before_revision.zip；原检测和功能证据包保持不变。
''',encoding='utf-8')
    p=OUT/'REVIEW_DISPOSITION.txt';s=p.read_text(encoding='utf-8')
    s='\n'.join(line for line in s.splitlines() if not line.startswith('???4??'))
    if '收尾第4轮' not in s:
        s+='\n\n收尾第4轮：Flash确认条件化恒等式无需同质/独立，接受双方纠正；在其明确限定的核对范围内未发现必须修改的事实、分母或统计错误，认为当前范围可交付。它未逐行重读所有最终文件，不将本结论写成独立完整审计或录用认可。\n'
    p.write_text(s,encoding='utf-8')
    for name in ('README.txt','STATUS.txt','FINAL_REPORT.txt'):
        text=(ROOT/name).read_text(encoding='utf-8');assert '???' not in text and any('\u4e00'<=c<='\u9fff' for c in text)
    print('UTF-8 delivery notes verified.')
if __name__=='__main__':main()
