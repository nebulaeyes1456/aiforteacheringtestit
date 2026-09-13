#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计算题 sympy 符号验算工具（用于人工审核/抽检，不做证明题）。

用法：
  python scripts/sympy_check.py "解方程 x^2 - 5*x + 6 = 0" "x=2 或 x=3"
  python scripts/sympy_check.py "已知 f(x)=x^2，求 f(3)" "9"

支持模式：
  1. 解方程/求根：从题干提取方程 → sympy.solve → 与答案中的数值集合比对；
  2. 求值：f(数字) 或 代入式 → sympy 求值比对。
"""
import re
import sys

try:
    import sympy as sp
except ImportError:
    print('需要 sympy：pip install sympy')
    sys.exit(1)

from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application  # noqa: E402

TR = standard_transformations + (implicit_multiplication_application,)


def nums(s):
    return {round(float(x), 6) for x in re.findall(r'-?\d+(?:\.\d+)?', s or '')}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    q, ans = sys.argv[1], sys.argv[2]
    x = sp.symbols('x')
    result = {'mode': 'unknown', 'note': '未识别出可验算的模式'}

    # 模式1：解方程
    eqs = re.findall(r'([^，。,；;]{0,60}?=\s*-?\d+(?:\.\d+)?)', q)
    if not eqs:
        eqs = re.findall(r'解方程[:：]?\s*([^,，。;；]+)', q)
    if eqs:
        try:
            parts = eqs[0].replace('＝', '=').split('=')
            expr_text = parts[0]
            rhs = float(parts[1]) if len(parts) > 1 else 0.0
            expr_text = re.sub(r'[\u4e00-\u9fff]+', ' ', expr_text)  # 去中文词
            expr_text = expr_text.replace('^', '**')  # K12 语境下 ^ 表示幂
            expr = parse_expr(expr_text, transformations=TR)
            sols = sp.solve(sp.Eq(expr, rhs), x)
            roots = set()
            for s in sols:
                try:
                    v = complex(sp.N(s))
                    if abs(v.imag) < 1e-9:  # K12 只比实数根
                        roots.add(round(v.real, 6))
                except Exception:
                    continue
            # 与答案数值集合比对（支持 ±、分数、负号）
            ans_text = ans.replace('或', ' ').replace(',', ' ').replace('，', ' ').replace('；', ' ')
            got = set()
            for m in re.finditer(r'±\s*(\d+(?:\.\d+)?)', ans_text):
                v = round(float(m.group(1)), 6)
                got.add(v)
                got.add(-v)
            for m in re.finditer(r'(?<!±)-?\d+(?:\.\d+)?(?:/\d+)?', ans_text):
                try:
                    t = m.group(0)
                    got.add(round(float(sp.Rational(t)), 6) if '/' in t else round(float(t), 6))
                except Exception:
                    continue
            if not got:
                got = nums(ans_text)
            match = roots == got or (got and got.issubset(roots) and roots.issubset(got))
            result = {
                'mode': '解方程',
                '方程': f'{expr} = {rhs}',
                'sympy 解': sorted(roots),
                '答案数值': sorted(got),
                '一致': bool(match),
            }
        except Exception as e:
            result = {'mode': '解方程', 'error': f'{type(e).__name__}: {str(e)[:100]}'}
    else:
        # 模式2：求值 f(数字) / 代入
        m = re.search(r'f\(x\)\s*=\s*([^,，。;；]+)', q)
        val = re.search(r'f\((-?\d+(?:\.\d+)?)\)', q)
        if m and val:
            try:
                expr = parse_expr(m.group(1).replace('^', '**'), transformations=TR)
                fx = sp.lambdify(x, expr, 'math')
                v = float(val.group(1))
                got = nums(ans)
                computed = round(float(fx(v)), 6)
                result = {
                    'mode': '求值',
                    'f(x)': m.group(1).strip(),
                    'x 取': v,
                    'sympy 计算': computed,
                    '答案数值': sorted(got),
                    '一致': bool(got and computed in got),
                }
            except Exception as e:
                result = {'mode': '求值', 'error': f'{type(e).__name__}: {str(e)[:100]}'}

    for k, v in result.items():
        print(f'{k}: {v}')


if __name__ == '__main__':
    main()
