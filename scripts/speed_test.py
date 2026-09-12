#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""并行核验速度自测：5 次并发解答 1 道题，打印耗时与结果。"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.verify_candidates import solve_many  # noqa: E402

q = '方程 x^2 - 4 = 0 的解是（ ）A. x=1  B. x=2  C. x=-2  D. x=±2'
t0 = time.time()
raw, errs = solve_many(q, 'choice')
elapsed = time.time() - t0
print(f'5 次并发解答耗时 {elapsed:.1f}s，结果 {raw}，错误 {errs}')
