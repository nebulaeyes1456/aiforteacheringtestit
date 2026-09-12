#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清洗题库：剔除答案/解析/分节标题等混入的坏题（客观判定，无需重新核验）。"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tutor import config  # noqa: E402

BAD_PATTERNS = [
    r'参考答案', r'正确答案', r'试题答案', r'答案详解',
    r'【?答[案】]', r'【?解[析】]', r'[（(]详?解[）)]',
    r'故选', r'因此选', r'故答案', r'答案为', r'答案[：:]',
    r'句意[：:]', r'[（(]\d+分[）)]', r'评分标准', r'计分规则', r'得分情况', r'作答',
    r'^[一二三四五六七八九十]+、',
    r'^第[一二三四五六七八九十\d]+部分',
]

RE = re.compile('|'.join(BAD_PATTERNS))


def is_bad(qtext):
    return bool(RE.search(qtext or ''))


def main():
    path = config.QUESTION_BANK
    bank = json.loads(path.read_text(encoding='utf-8'))
    qs = bank['questions']
    before = len(qs)
    bad = [q for q in qs if is_bad(q.get('question', ''))]
    bad_ids = {q['id'] for q in bad}
    kept = [q for q in qs if q['id'] not in bad_ids]
    bank['questions'] = kept
    path.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'清洗前 {before} 道，剔除 {len(bad)} 道，剩余 {len(kept)} 道')
    from collections import Counter
    print('剔除按学科:', dict(Counter(q.get('subject') for q in bad)))
    print('样例:')
    for q in bad[:5]:
        print('  -', q.get('subject'), (q.get('question') or '')[:60].replace('\n', ' '))


if __name__ == '__main__':
    main()
