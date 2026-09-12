#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统计 9 个学科栏目文章总数与年份分布"""
import re, ssl, urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

SUBJECTS = {'数学': 'sx', '物理': 'wl', '化学': 'hx', '英语': 'yy', '语文': 'yw',
            '生物': 'sw', '历史': 'ls', '地理': 'dl', '政治': 'zz'}


def g(u):
    req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=25, context=CTX) as r:
        return r.read().decode('gb18030', 'ignore')


for name, code in SUBJECTS.items():
    try:
        t = g(f'https://www.shijuan1.com/a/sj{code}/')
        arts = re.findall(r'<a[^>]+href="(/a/sj[^"]+\.html)"[^>]*>\s*([^<]{4,80}?)\s*</a>', t)
        titles = [a[1] for a in arts if '/a/sj' in a[0] and 'html' in a[0]]
        years = {}
        for title in titles:
            m = re.search(r'(20\d{2})', title)
            if m:
                years[m.group(1)] = years.get(m.group(1), 0) + 1
        gaokao = sum(1 for x in titles if '高考' in x)
        zhongkao = sum(1 for x in titles if '中考' in x)
        print(f'{name}: 共 {len(titles)} 篇 | 高考 {gaokao} 中考 {zhongkao} | 年份分布 {dict(sorted(years.items()))}')
    except Exception as e:
        print(f'{name}: ERR {type(e).__name__} {str(e)[:60]}')
