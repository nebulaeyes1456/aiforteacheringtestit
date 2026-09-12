#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""更新 .env 中的预算限额（更新已有行或追加），不影响其他配置。"""
import sys

path = sys.argv[1]
updates = {'TUTOR_DAILY_CAP': sys.argv[2] if len(sys.argv) > 2 else '30',
           'TUTOR_API_BUDGET': sys.argv[3] if len(sys.argv) > 3 else '500'}
with open(path, encoding='utf-8') as f:
    lines = f.read().splitlines()
out, seen = [], set()
for ln in lines:
    key = ln.split('=', 1)[0].strip() if '=' in ln else ''
    if key in updates:
        out.append(f'{key}={updates[key]}')
        seen.add(key)
    else:
        out.append(ln)
for k, v in updates.items():
    if k not in seen:
        out.append(f'{k}={v}')
with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out) + '\n')
print('已更新限额:', ', '.join(f'{k}={v}' for k, v in updates.items()))
