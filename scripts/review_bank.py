#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""人工审核证明/新定义题（status=review 的题）。

用法：
  python scripts/review_bank.py list                        # 列出待审核题
  python scripts/review_bank.py show <id>                   # 显示完整题目与解答
  python scripts/review_bank.py approve <id>                # 通过 → status=ready 上线
  python scripts/review_bank.py reject <id>                 # 不通过 → 移入 rejected 档案
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tutor import config  # noqa: E402

REJECTED_FILE = config.DATA_DIR / 'rejected_manual.json'


def load():
    return json.loads(config.QUESTION_BANK.read_text(encoding='utf-8'))


def save(bank):
    config.QUESTION_BANK.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    bank = load()
    qs = bank['questions']
    cmd = args[0]

    if cmd == 'list':
        review = [q for q in qs if q.get('status') == 'review']
        print(f'待人工审核：{len(review)} 道')
        for q in review:
            print(f"  [{q['id']}] {q.get('subject')} {q.get('year')} | {(q['question'] or '')[:50].replace(chr(10), ' ')}")
        return

    qid = args[1] if len(args) > 1 else ''
    found = next((q for q in qs if q['id'] == qid), None)
    if not found:
        print('找不到该题 ID')
        return

    if cmd == 'show':
        print('题目：', found['question'])
        print('答案：', found.get('official_answer'))
        print('验证：', found.get('verify'))
        print('AI解答：', found.get('solution'))
        return

    if cmd == 'approve':
        found['status'] = 'ready'
        found['verify'] = (found.get('verify') or '') + '；人工审核通过'
        save(bank)
        print(f'{qid} 已上线')
        return

    if cmd == 'reject':
        found['status'] = 'rejected'
        rejected = []
        if REJECTED_FILE.exists():
            try:
                rejected = json.loads(REJECTED_FILE.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                rejected = []
        rejected.append(found)
        REJECTED_FILE.write_text(json.dumps(rejected, ensure_ascii=False, indent=2), encoding='utf-8')
        bank['questions'] = [q for q in qs if q['id'] != qid]
        save(bank)
        print(f'{qid} 已移除并归档到 rejected_manual.json')
        return

    print(__doc__)


if __name__ == '__main__':
    main()
