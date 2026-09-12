#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查第一试卷网各栏目分页深度与年份跨度"""
import re, ssl, sys, urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
        return r.read().decode('gb18030', 'ignore')


cols = ['/a/sjsxgk/', '/a/sjsxzk/', '/a/sjwlgk/', '/a/sjhxgk/', '/a/sjywgk/', '/a/sjyygk/',
        '/a/sjswgk/', '/a/sjlsgk/', '/a/sjdlgk/', '/a/sjzzgk/']
for col in cols:
    try:
        txt = get('https://www.shijuan1.com' + col)
        titles = re.findall(r'<a[^>]+href="(/a/sj[^"]+\.html)"[^>]*>\s*([^<]{4,80}?)\s*</a>', txt, re.S)
        years = sorted({m.group(1) for t in titles for m in [re.search(r'(20\d{2})', t[0])] if m})
        # 找分页最大页码
        pages = re.findall(r'(?:list|index)_(\d+)\.html', txt)
        maxpage = max((int(p) for p in pages), default=1)
        print(f'{col} 首屏 {len(titles)} 篇, 年份 {years}, 分页迹象 max={maxpage}')
    except Exception as e:
        print(f'{col} ERR {type(e).__name__}')
