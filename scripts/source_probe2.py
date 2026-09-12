#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器：核查 EduData / LiveK12Bench 等数据集的实际内容与许可"""
import ssl, urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def get(url, maxb=30000, timeout=25):
    req = urllib.request.Request(url, headers={'User-Agent': 'K12Probe/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read(maxb)
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:100]}"


targets = [
    ('EduData(toolkit) README', 'https://raw.githubusercontent.com/tswsxk/EduData/master/README.md'),
    ('LiveK12Bench LICENSE', 'https://raw.githubusercontent.com/Tencent-QQMM/LiveK12Bench/main/LICENSE'),
    ('HF guoyx18/EduData README', 'https://huggingface.co/datasets/guoyx18/EduData/raw/main/README.md'),
    ('HF Shawn-wxh/livek12bench README', 'https://huggingface.co/datasets/Shawn-wxh/livek12bench/raw/main/README.md'),
]
for name, url in targets:
    s, b = get(url)
    print(f"\n===== {name}  HTTP {s}")
    if s == 200:
        print(b.decode('utf-8', 'ignore')[:2200])
    else:
        print(str(b)[:200])
