#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查看数学试卷栏目页：子栏目与分页"""
import re, ssl, urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def g(u):
    req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
        return r.read().decode('gb18030', 'ignore')


t = g('https://www.shijuan1.com/a/sjsx/')
subs = re.findall(r'href="(/a/sj[a-z0-9_]+/)"[^>]*>\s*([^<]{2,30}?)\s*</a>', t)
print('子栏目:', sorted(set(subs)))
pags = sorted(set(re.findall(r'href="([^"]*(?:list|index|page)[^"]*)"', t)))
print('分页线索:', pags[:12])
arts = re.findall(r'<a[^>]+href="(/a/sj[^"]+\.html)"[^>]*>\s*([^<]{4,80}?)\s*</a>', t)
print('文章:', len(arts), [a[1][:40] for a in arts[:6]])
