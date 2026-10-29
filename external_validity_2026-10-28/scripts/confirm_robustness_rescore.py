"""Factual clarification without disclosing or negotiating another reviewer's score."""
import json
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'records/jsep_rescore_after_robustness_20261029'


def main():
    session = json.loads((DEST / 'usage.json').read_text(encoding='utf-8'))['session']
    request = '''请继续本轮独立评阅，只作事实与量表口径核对，不要求加分，也不要求与主助手一致。
我不提供主助手分数。原始评分会完整保留。你可以维持71、升分或降分，但请让最终理由与稿件实际内容对应。
下面重附当前稿件的原文，没有新增数据，没有为回应评阅临时改稿。请核对以下具体问题：

1. 你两次说“摘要以183/85开头/放在最前”。实际摘要前几句依次是维护问题、固定SEW、三套队列、搜索比较与校准，183/85在后半部。数字是否仍过于突出可以判断，但请区分文本事实与叙事偏好。
2. 你建议“剔除LineLengthCheck非法产物，以通过编译子集重算joint yield，并对170个字符独有clean新增测试”。主文功能表的joint定义已经要求原始父子、标记父子四个版本全部通过指定测试，再加检测。已记录的ndex++i编译失败不计入183次joint成功；失败仍留432分母。170个额外字符clean并非未测新程序，而是既有字符政策管线的结果，相关分数/测试已经记录；其中98个为四版本通过并检出的joint成功。共有135个字节相同输出才复用已有记录，且两政策均保留无法测试结果。测试不能证明所有语义正确，但不能据某个已被判为失败的程序，推断它混入joint成功。你可以质疑回溯重放的现实性、测试覆盖、环境可用性；请明确其与“未经过功能筛选”“必须再测才能有joint”不同。若仍建议额外编译诊断，请说明要回答哪个现有端点未回答的问题，不应移除失败分母来美化成功率。
3. 你说当前主卖点是“结构搜索更优”，建议把主贡献改为操作条件；引言和结论已明确给出RQ1–RQ3，主文也直接写非等实际FPR、强对照差距小及限制优胜主张。若仍存在强度不匹配，请指出具体原句，避免把本稿未作出的普遍优胜主张当作前提。
4. 你的等实际FPR与等效性建议需区分：(a)用后期阴性选阈值只可作为事后ROC/区分度诊断，不能冒充早期拟合后期部署评估；(b)非显著不等于等效，非劣/等效需要有意义的界值和充分设计。若你仍认为这是当前操作条件主张的必要补证，请解释为什么，不以加做这些分析作为自动加分条件。
5. 你在Scope和外部效度均以单一SEW/两种真实项目语言扣分，可能重复。共同量表要求同一缺点避免跨维度重复扣分。可维持总体判断，但请重新厘清每维不同的理由。统计项所谓“六方法×六项目未多重校正”：当前这些是明确声明的描述性敏感性区间，而非宣称族水平显著性；控制实验的三个预定主比较另有Holm。请区分“缺少同时推断能力”和“现有推断错误/必须校正”的指控。
6. 你说主要来自“同项目、同时期”。这里用早期校准、后期评价，并非同时期抽样；外部与早期本地对比也不能单独分离项目、时期及其他分布差异的因果效应。主文已列早期原始6.44–6.58%和早期配对5.31–5.44%，明确非普遍因果论断。配对本身的增益不大可以保留为贡献评价，请避免称数据证明了同项目/时期的独立机制。

请给出：A.哪些误读撤回、哪些质疑坚持；B.最终七项分数、正确总和和变化依据（不因措辞纠正自动加分）；C.两项0–10诊断分；D.最重要的科学拒稿风险、是否值得按JSEP Empirical继续准备及是否确有必须新增的实验。若认为现稿已经完成了你先前某项建议，请直说，不再把它列为待完成。不要调用工具。中文约1200–1800字。
'''
    sources = []
    for name in ('maintenance_abstract.tex', 'maintenance_introduction.tex', 'temporal_external.tex',
                 'robustness_checks.tex', 'maintenance_conclusion.tex'):
        sources.append('\nCURRENT UNCHANGED FILE: ' + name + '\n' + (ROOT / 'paper' / name).read_text(encoding='utf-8'))
    sources.append('\nCURRENT UNCHANGED INTERVAL DESCRIPTION:\n' + (ROOT / 'paper/temporal_supplement.tex').read_text(encoding='utf-8')[
        (ROOT / 'paper/temporal_supplement.tex').read_text(encoding='utf-8').index('\\subsection{Paired detection contrasts}'):])
    full = request + '\n'.join(sources)
    wrapper = textwrap.TextWrapper(width=150, break_long_words=True, break_on_hyphens=False,
                                   replace_whitespace=False, drop_whitespace=False)
    chunks, current = [], ''
    for line in full.splitlines():
        for wrapped in wrapper.wrap(line) or ['']:
            if len(current) + len(wrapped) + 1 > 10000:
                chunks.append(current)
                current = ''
            current += wrapped + '\n'
    if current:
        chunks.append(current)
    files = []
    for i, chunk in enumerate(chunks, 1):
        path = DEST / f'clarification_{i:02d}.txt'
        assert not path.exists()
        path.write_text(f'CLARIFICATION PART {i} OF {len(chunks)}\n' + chunk, encoding='utf-8')
        files.append(path)
    def quote(value):
        return "'" + str(value).replace("'", "''") + "'"
    command = "& 'C:/Users/Administrator/AppData/Roaming/npm/opencode.ps1' run "
    command += quote('Check the attached factual clarification against the already supplied full manuscript. Confirm or revise your independent score; no increase is requested. Another score is not disclosed. Answer in Chinese; do not call tools.')
    command += ' -s ' + quote(session) + ' -m deepseek/deepseek-flash --format json '
    command += ' '.join('-f ' + quote(p) for p in files)
    launcher = DEST / 'confirm.ps1'
    launcher.write_text(command + '\nexit $LASTEXITCODE\n', encoding='utf-8-sig')
    raw, error = DEST / 'confirmed.raw.jsonl', DEST / 'confirmed.stderr.txt'
    print(json.dumps({'session': session, 'parts': len(files), 'new_results': False, 'other_scores_disclosed': False}), flush=True)
    with raw.open('xb') as out, error.open('xb') as err:
        process = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(launcher)],
                                 cwd=ROOT.parent, stdout=out, stderr=err, timeout=900)
    assert process.returncode == 0, 'Confirmation failed; see stderr.'
    answers, finishes = [], []
    for line in raw.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        part = event.get('part', {})
        if event.get('type') == 'error':
            raise RuntimeError(event)
        if event.get('type') == 'text':
            answers.append(part.get('text', ''))
        if event.get('type') == 'step_finish':
            finishes.append({key: part.get(key) for key in ('reason', 'cost', 'tokens')})
    assert answers
    target = DEST / 'DEEPSEEK_CONFIRMED_SCORE.txt'
    target.write_text('\n\n'.join(answers), encoding='utf-8')
    (DEST / 'confirmed_usage.json').write_text(json.dumps({'session': session, 'steps': finishes}, indent=2), encoding='utf-8')
    print(json.dumps({'answer': str(target), 'session': session}), flush=True)


if __name__ == '__main__':
    main()
