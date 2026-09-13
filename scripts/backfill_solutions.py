#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给题库逐题生成「解题步骤」（AI 完整解答），存入 question_bank.json 的 solution 字段。

- 已含 solution 的题跳过（可断点续跑）
- 8 路并行，每 20 题增量落盘
- 成本估算：约 ¥0.0012/题 × 3000 题 ≈ ¥4~8（预算已放开）

用法：python scripts/backfill_solutions.py [--workers 8]
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # app/
ROOT = Path(__file__).resolve().parent.parent

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from tutor import client, config, prompts  # noqa: E402

BANK = config.QUESTION_BANK


def solve_one(q):
    subject = q.get('subject') or '数学'
    try:
        text = client.chat(prompts.solve(q['question'], subject), temperature=0.3, max_tokens=600)
        return ('ok', q['id'], text)
    except client.BudgetExceededError as e:
        return ('err', q['id'], str(e))
    except Exception as e:
        return ('err', q['id'], f'{type(e).__name__}: {str(e)[:80]}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=8)
    args = ap.parse_args()

    bank = json.loads(BANK.read_text(encoding='utf-8'))
    questions = bank['questions']
    todo = [q for q in questions if not (q.get('solution') and len(str(q.get('solution'))) > 20)]
    print(f'共 {len(questions)} 题，待生成步骤 {len(todo)} 题（{args.workers} 路并行）')

    done = 0
    errs = 0
    t0 = time.time()
    idx = {q['id']: q for q in questions}

    def handle(result):
        nonlocal done, errs
        status, qid, text = result
        if status == 'ok':
            idx[qid]['solution'] = text.strip()
            done += 1
        else:
            errs += 1
            print(f'  [ERR] {qid}: {text[:80]}')
        if (done + errs) % 20 == 0:
            BANK.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'  …已完成 {done} 题 / 出错 {errs}，用时 {time.time()-t0:.0f}s')

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(solve_one, q) for q in todo]
        for fut in futures:
            try:
                handle(fut.result())
            except Exception as e:
                errs += 1
                print(f'  [ERR] future: {type(e).__name__}')

    BANK.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n完成：生成 {done} 题，出错 {errs} 题，总用时 {time.time()-t0:.0f}s')
    print('花费参考：', client.budget_status())


if __name__ == '__main__':
    main()
