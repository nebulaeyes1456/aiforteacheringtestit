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
    # 无编号小题拼接题：○/□填比较、一行多个算式
    r'[○□▢]\s*里?填',
    r'\d+\s*[×÷+\-]\s*\d+\s+\d+\s*[×÷+\-]\s*\d+',
]

OPTION_MARK = re.compile(r'[A-D]\s*[.．、]')
EMPTY_OPTIONS_RE = re.compile(r'[A-D]\s*[.．、]\s*[A-D]\s*[.．、]')
FIG_RE = re.compile(r'如图|图所示|图中|下图|如图所示|下列图|图象所示|图像所示')

RE = re.compile('|'.join(BAD_PATTERNS), re.MULTILINE)


def is_bad(qtext):
    text = qtext or ''
    if RE.search(text):
        return True
    # 选项相邻（中间无内容）→ 公式图片化导致的空选项
    if EMPTY_OPTIONS_RE.search(text):
        return True
    # 选择题但题干正文过短（题目本体是图片）
    m = OPTION_MARK.search(text)
    if m and len(text[:m.start()].strip()) < 6:
        return True
    # 图示题：前端尚不支持显示图，暂移入 OCR 队列
    if FIG_RE.search(text):
        return True
    return False


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
