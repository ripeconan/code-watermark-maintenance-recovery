"""Export only allowlisted metadata from the completed fresh scoring session."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'records/jsep_rescore_after_robustness_20261029'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    usage = json.loads((DEST / 'usage.json').read_text(encoding='utf-8'))
    session = usage['session']
    assert session.startswith('ses_') and session.isalnum() is False
    command = "& 'C:/Users/Administrator/AppData/Roaming/npm/opencode.ps1' export '" + session + "'"
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command],
                            capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert result.returncode == 0, 'Session export failed; raw export not printed.'
    data = json.loads(result.stdout)
    assistants, users, attachment_markers = [], [], set()
    for message in data['messages']:
        info = message.get('info', {})
        if info.get('role') == 'assistant':
            assistants.append({key: info.get(key) for key in
                               ('id', 'providerID', 'modelID', 'time', 'cost', 'tokens', 'finish')})
        elif info.get('role') == 'user':
            users.append({key: info.get(key) for key in ('id', 'time')})
            for part in message.get('parts', []):
                value = part.get('text', '')
                for i in range(1, 20):
                    if f'PART {i} OF 19' in value:
                        attachment_markers.add(i)
    assert assistants, 'No actual assistant metadata.'
    assert all(a['providerID'] == 'deepseek' and a['modelID'] == 'deepseek-flash' for a in assistants)
    assert all(a['time'].get('completed') for a in assistants)
    seal = json.loads((DEST / 'self_seal.json').read_text(encoding='utf-8'))
    assert digest(DEST / 'SELF_SCORE.txt') == seal['self_score_sha256']
    assert all(digest(ROOT / 'paper' / n) == h for n, h in seal['paper_pdf_hashes'].items())
    audit = {
        'session': session, 'user_messages': users, 'assistant_messages': assistants,
        'attached_part_markers_in_exported_text': sorted(attachment_markers),
        'self_score_unchanged': True, 'paper_pdf_hashes_unchanged': True,
        'answer_sha256': digest(DEST / 'DEEPSEEK_SCORE.txt'),
        'raw_events_sha256': digest(DEST / 'deepseek.raw.jsonl'),
        'interpretation': 'Actual local OpenCode session metadata; not official billing evidence or external peer review.',
    }
    confirmed = DEST / 'DEEPSEEK_CONFIRMED_SCORE.txt'
    if confirmed.exists():
        audit['confirmed_answer_sha256'] = digest(confirmed)
        audit['confirmed_raw_sha256'] = digest(DEST / 'confirmed.raw.jsonl')
    target = DEST / ('model_audit_confirmed.json' if confirmed.exists() else 'model_audit.json')
    target.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
