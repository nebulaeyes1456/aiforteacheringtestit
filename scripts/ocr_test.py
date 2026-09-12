#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器：Pix2Text 公式 OCR 测试"""
import sys
from pix2text import Pix2Text

p2t = Pix2Text.from_config()
for f in sys.argv[1:]:
    try:
        r = p2t.recognize_formula(f)
        print(f, '=>', r)
    except Exception as e:
        print(f, 'ERR', type(e).__name__, str(e)[:200])
