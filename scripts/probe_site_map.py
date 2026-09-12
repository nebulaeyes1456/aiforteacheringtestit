#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出第一试卷网首页所有栏目入口，绘制栏目地图"""
import re, ssl, urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def g(u):
    req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
        return r.read().decode('gb18030', 'ignore')


t = g('https://www.shijuan1.com/')
# 导航链接：/a/xxx/ 栏目
cols = re.findall(r'href="(/a/[a-z0-9_]+/)"[^>]*>\s*([^<]{2,20}?)\s*</a>', t)
seen = {}
for u, name in cols:
    if u not in seen:
        seen[u] = name
for u, name in sorted(seen.items()):
    print(u, name)
