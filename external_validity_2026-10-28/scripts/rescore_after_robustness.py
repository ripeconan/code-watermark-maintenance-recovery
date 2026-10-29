"""Seal an independent score, then request a fresh version-bound DeepSeek review."""
import datetime
import hashlib
import json
import re
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'records/jsep_rescore_after_robustness_20261029'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def expand(path):
    def replace(match):
        target = ROOT / 'paper' / match[1]
        return expand(target if target.suffix else target.with_suffix('.tex'))
    return re.sub(r'\\input\{([^}]+)\}', replace, path.read_text(encoding='utf-8'))


def main():
    DEST.mkdir(exist_ok=False)
    hashes = {n: digest(ROOT / 'paper' / n) for n in ('main.pdf', 'supplement.pdf')}
    expected = {
        'main.pdf': '62c24123fc295bdd938502026f7e761e065b1a707967a098ac96debe384f3175',
        'supplement.pdf': '85822c61f39da5361ec2381fb8f37d6ab4b142b547fa4567a376fa7daccc992d',
    }
    assert hashes == expected, hashes
    created = datetime.datetime.now(datetime.timezone.utc).isoformat()
    own = '''主助手独立评分：81/100。2026-10-29，P0–P3修改完成后。
对象为21页主文及28页补充材料。本分数先于本轮DeepSeek调用封存，未向其提供，也不随其结果追调。
沿用原JSEP Empirical内部量表；不是官方量表、录用概率、期刊平均论文水平或外部同行评审。

1. Scope与读者价值：13/15（不变）。
固定水印语料在维护后能否恢复、误报控制和执行可用性，具有软件维护和质量评价价值。三个研究问题更明确，但未新增实际部署需求或使用频率证据，因此不因改写加分。
2. 新知识与贡献：17/25（不变）。
实证价值更具体：同一批尝试上，两种重放规则的共同干净输出完全相同，联合成功差异可定位到重放可用性；校准预算分析区分了未知阴性导致的无穷阈值与缺乏正例证据。这些是有用的条件性知识。
但同步、搜索、校准与执行验证均已有直接近邻；新文献矩阵也更清楚地显示已有工作的覆盖程度。新结果未使结构扩展优于强基线的幅度扩大，也未证明这些条件性发现具有跨水印的一般性。贡献仍达不到强方法创新水平。新增结果与更准确的先行工作定位综合后维持17，而非按实验数量加分。
3. 实验设计与证据：18/20（不变）。
强对照、分阶段队列、失败保留和全套测试仍有力度。冻结的配对重放敏感性填补了重要检查，135个共同输出完全相同使已有分数和测试复用合理；不能将其说成新增135次全套测试。
现已量化重放规则影响，但原始问题没有消失：回溯重放仍不能观测开发者自然维护和解决冲突的行为。功能证据仍来自144个预选转变，原始可执行性项目差异大。补强的是对现有证据的解释，尚不足把整体设计评为接近完备。
4. 统计与理论论证：14/15（原13，增加1）。
5000次有限池子集抽样直接量化了校准选择的变动；保留配对方法/密钥结构，准确区别经验选择分位数与未来置信保证，缺失阴性触发无穷阈值有精确超几何计算核验。
这是正确应用既有统计工具的加分，不是新数学理论。仍未提供统一的跨层级未来不确定性推断；同名义目标下各方法实际误报不同，不支持等风险优胜解释。14评价论证与当前主张的匹配度，并非发现新定理的程度。
5. 结论边界与外部效度：7/10（不变）。
边界更清楚，但单一SEW、目的性项目样本、真实时间队列限Python/Java的事实没有变化；两种重放规则并不是两个独立维护群体。共同干净输出无差异，也没有增加分歧干净程序的功能证据。外部效度的实质覆盖没有提高。
6. 写作组织与成稿程度：8/10（不变）。
三个研究问题和贡献表更连贯；主文、补充、摘要、结论口径一致。已执行编译及49页视觉检查，不能由此声称完成专业语言编辑。
主文由19增至21页，材料结构与多种分母仍给读者较大负担。已准确收敛主张，但还可以压缩重复边界、强化面向维护读者的决策解释。页数不是自动不合规判断。
7. 可复验性与数据可得性：4/5（不变）。
本地交付包、逐文件哈希、冻结配置、复用映射和原始记录齐全，新增结果可追踪。公开可访问的复现入口仍未发布；内部核验不等于外部独立复现。

合计：13+17+18+14+7+8+4=81。相对上一版80分，只增加统计论证1分。
诊断性子分（不额外计入总分）：算法/数学新颖性3/10；实证新知识价值7/10。
判断：值得继续以JSEP Empirical为目标准备投稿；不是可直接点击提交的完整材料，公开工件与真实作者/声明等仍需完成。
最大科学拒稿风险：审稿人认为这些条件性发现主要是已知搜索/校准原则在单一SEW实现及回溯重放上的验证，新增普遍认识仍有限。
优先事项：整合公开可访问工件；压缩叙事、突出三个研究问题能支持的决策；只在需要扩大科学主张时，再为可迁移机制预设第二系统验证。不能把第二系统或新实验当本轮已得分依据。
我比此前DeepSeek更看重现有实证证据；本次评分维持原量表尺度，不因预期对方会低分而迁就。分数的小幅变化不宜解释成精确测量。
'''
    (DEST / 'SELF_SCORE.txt').write_text(own, encoding='utf-8')
    save_json(DEST / 'self_seal.json', {
        'created_utc': created, 'scores': [13, 17, 18, 14, 7, 8, 4], 'total': 81,
        'self_score_sha256': digest(DEST / 'SELF_SCORE.txt'), 'paper_pdf_hashes': hashes,
        'sealed_before_model_call': True,
    })

    instructions = '''请作为独立评阅者，对附件中的当前完整稿件按JSEP Empirical定位评分，中文回答。
仅使用这次附件；不要调用任何工具，不修改文件。你是OpenCode中的deepseek/deepseek-flash。
主助手已经封存自己的评分，但不会向你提供它或任何历史分数。不要猜测、追求一致或为了安慰作者加分。
这是内部评估，不是JSEP官方评分表、录用概率或对期刊平均论文水平的统计估计。
按附件同一量表给七项整数分、各项具体证据与扣分理由、正确加总的总分。避免一个缺点在多个维度重复扣分。
评价现有实证知识是否值得发表；不要求每篇实证论文SOTA或新定理，不以工作量、语言数量、披露诚实本身作为新颖性。
另给算法/数学新颖性和实证新知识价值两个0—10诊断分，不与100分相加。
回答是否值得投JSEP、现稿能否直接提交、最大的科学拒稿风险、最多三项优先改进及是否必须新增实验。
特别检查科学主张与证据是否匹配，不因作者限定了结论就自动认为贡献充分，也不把限定本身当事实错误。
你收到完整展开主文和补充材料的LaTeX、参考文献与事实说明。没有自行运行工件、看PDF版式、阅读全文引用或检索最新近邻；请准确限定本轮审阅范围。
每个编号附件是完整材料的连续部分，请通读全部。中文答复约1500—2200字，保留明确的七维评分表。
'''
    rubric = (ROOT / 'records/JSEP_SHARED_RUBRIC_20261029.txt').read_text(encoding='utf-8')
    facts = '''VERSION AND EVIDENCE FACTS, NOT AN EVALUATION:
Current main PDF has 21 pages and supplement 28. Both were compiled and locally visually checked; you receive text only. These are the completed current files, not a proposed plan.
Three repository frames (707,640,1375 transitions) are separately analyzed. Six-project temporal cohort:688 earlier and687 later transitions;three fixed keys are repeated measurements,not independent programs.
Functional cohort:144 preselected transitions,87 paths,432 key-specific attempts;966 deduplicated jobs. Passing original pairs294;all-four passing221 in the canonical pipeline. Canonical joint detections:Official159,Single181,Struct64183,Nearest64178,Dict64172,DictPair64176.
The post-outcome calibration-budget analysis draws5000 subsets at each m20,40,80 from the existing earlier pools,holds later outcomes fixed,and retains identical subset IDs across methods and keys. Reported percentiles are finite-pool subset-selection quantiles,not population or future confidence intervals.
The paired replay-policy analysis uses the same432 attempts:33 embedding abstentions,1 pre-replay error,398 eligible for reconstruction. Character replay has305 clean and93 conflict;line replay has135 clean and263 conflict. All135 shared clean programs are byte-identical;there are170 character-only clean and93 both-conflict. Exact matching archived scores/tests are reused;there are ZERO new detector-scoring calls or full-suite executions in this replay analysis. Joint counts change to73,84,85,80,78,80 respectively. Among135 common clean outputs93 pass all four versions. The canonical221 includes19 embedding-abstention unchanged programs,so these two raw all-four counts have different eligibility gates.
The primary source comparison acknowledges SEW context survival,CREST calibration/population transfer,SynMark routing and functionality,signature filtering,and the public CodeMarkBench artifact. CodeMarkBench is a software/data artifact,not asserted to be a peer-reviewed paper. Evaluate novelty from the evidence presented;you have not independently reviewed those source papers here.
The manuscript and locally verified archive contain protocols,data provenance,licenses,scores,test logs,and analysis scripts. The new delivery archive has375 files with per-file SHA256 verification and a local+server backup. No public artifact URL has yet been released;no external independent reproduction has occurred. Author details and final public data-access statement are not complete. Local audit or a model's review is not peer review.
'''
    sections = [instructions, rubric, facts]
    for name in ('main', 'supplement'):
        sections.append('CURRENT ' + name.upper() + ' COMPLETE EXPANDED SOURCE\n' + expand(ROOT / 'paper' / (name + '.tex')))
        sections.append('CURRENT ' + name.upper() + ' REFERENCES\n' + (ROOT / 'paper' / (name + '.bbl')).read_text(encoding='utf-8'))
    whole = '\n\n'.join(sections)
    wrapper = textwrap.TextWrapper(width=150, break_long_words=True, break_on_hyphens=False,
                                   replace_whitespace=False, drop_whitespace=False)
    lines = []
    for line in whole.splitlines():
        lines.extend(wrapper.wrap(line) or [''])
    chunks, current = [], ''
    for line in lines:
        if len(current) + len(line) + 1 > 10000:
            chunks.append(current)
            current = ''
        current += line + '\n'
    if current:
        chunks.append(current)
    files = []
    for i, chunk in enumerate(chunks, 1):
        path = DEST / f'part_{i:02d}.txt'
        path.write_text(f'PART {i} OF {len(chunks)}\n' + chunk, encoding='utf-8')
        assert max(map(len, path.read_text(encoding='utf-8').splitlines())) <= 160
        files.append(path)
    save_json(DEST / 'input_manifest.json', {
        'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'requested_model': 'deepseek/deepseek-flash', 'fresh_session': True,
        'paper_pdf_hashes': hashes, 'self_score_sha256': digest(DEST / 'SELF_SCORE.txt'),
        'self_score_attached': False, 'previous_scores_attached': False,
        'characters_before_wrapping': len(whole),
        'parts': [{'file': p.name, 'sha256': digest(p), 'bytes': p.stat().st_size} for p in files],
    })
    def quote(value):
        return "'" + str(value).replace("'", "''") + "'"
    prompt = 'Read ALL numbered files as one complete manuscript. Independently grade the current paper using the attached shared JSEP Empirical rubric. Answer in Chinese. Do not call tools.'
    command = "& 'C:/Users/Administrator/AppData/Roaming/npm/opencode.ps1' run " + quote(prompt)
    command += ' -m deepseek/deepseek-flash --format json ' + ' '.join('-f ' + quote(p) for p in files)
    launcher = DEST / 'run.ps1'
    launcher.write_text(command + '\nexit $LASTEXITCODE\n', encoding='utf-8-sig')
    print(json.dumps({'sealed': True, 'parts': len(files), 'input_characters': len(whole)}), flush=True)
    raw, error = DEST / 'deepseek.raw.jsonl', DEST / 'deepseek.stderr.txt'
    with raw.open('xb') as out, error.open('xb') as err:
        process = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(launcher)],
                                 cwd=ROOT.parent, stdout=out, stderr=err, timeout=1200)
    assert process.returncode == 0, f'OpenCode exit={process.returncode}; see {error}'
    answers, finishes, sessions, event_types = [], [], set(), set()
    for line in raw.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        event_types.add(event.get('type'))
        part = event.get('part', {})
        if event.get('sessionID'):
            sessions.add(event['sessionID'])
        if part.get('sessionID'):
            sessions.add(part['sessionID'])
        if event.get('type') == 'error':
            raise RuntimeError(event)
        if event.get('type') == 'text':
            answers.append(part.get('text', ''))
        if event.get('type') == 'step_finish':
            finishes.append({k: part.get(k) for k in ('reason', 'cost', 'tokens')})
    assert answers and len(sessions) == 1, (len(answers), sessions)
    (DEST / 'DEEPSEEK_SCORE.txt').write_text('\n\n'.join(answers), encoding='utf-8')
    save_json(DEST / 'usage.json', {'session': next(iter(sessions)), 'steps': finishes, 'event_types': sorted(event_types)})
    assert hashes == {n: digest(ROOT / 'paper' / n) for n in hashes}
    seal = json.loads((DEST / 'self_seal.json').read_text(encoding='utf-8'))
    assert seal['self_score_sha256'] == digest(DEST / 'SELF_SCORE.txt')
    print(json.dumps({'answer': str(DEST / 'DEEPSEEK_SCORE.txt'), 'session': next(iter(sessions)), 'event_types': sorted(event_types)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
