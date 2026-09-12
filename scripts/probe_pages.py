#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试 DedeCMS 分页 URL 格式（list_N / index_N）"""
import re, ssl, urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def g(u):
    req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        return urllib.request.urlopen(req, timeout=15, context=CTX).read().decode('gb18030', 'ignore')
    except Exception as e:
        return 'ERR ' + type(e).__name__


for p in ['/a/sjwlgk/list_2.html', '/a/sjwlgk/index_2.html', '/a/sjwlgk/list_3.html']:
    t = g('https://www.shijuan1.com' + p)
    if t.startswith('ERR'):
        print(p, t)
        continue
    arts = re.findall(r'<a[^>]+href="(/a/sj[^"]+\.html)"[^>]*>\s*([^<]{4,80}?)\s*</a>', t)
    print(p, '文章', len(arts), [a[0][:40] for a in arts[:4]])
    # 找出该页面上所有分页链接样式
    pags = sorted(set(re.findall(r'(?:list|index)_(\d+)\.html', t)))
    print('   分页链接页号:', pags[:12])
