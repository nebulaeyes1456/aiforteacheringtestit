#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地：解析第一试卷网/考试酷首页结构，判断抓取可行性"""
import re, ssl, urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def get(url, timeout=15):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36'})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.status, r.read(200000)


def links_of(url, encodings=('utf-8', 'gb18030')):
    s, raw = get(url)
    txt = None
    for enc in encodings:
        try:
            txt = raw.decode(enc)
            break
        except Exception:
            continue
    print(f"\n== {url}  HTTP {s}")
    if txt is None:
        print("  decode fail"); return
    pairs = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', txt, re.S)
    out = []
    for href, text in pairs:
        text = re.sub(r'<[^>]+>', '', text).strip()[:30]
        if not text or text in ('首页', '注册', '登录'):
            continue
        out.append((href, text))
    seen = set()
    for href, text in out:
        if href in seen:
            continue
        seen.add(href)
        print(f"  {text}  ->  {href}")


links_of('https://www.shijuan1.com/')
links_of('https://www.examcoo.com/')
