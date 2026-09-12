#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试站点搜索（robots 允许的 /plus/search.php）与 sitemap"""
import re, ssl, urllib.parse, urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def g(u, referer=None):
    hdr = {'User-Agent': 'Mozilla/5.0'}
    if referer:
        hdr['Referer'] = referer
    req = urllib.request.Request(u, headers=hdr)
    with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
        return r.status, r.read().decode('gb18030', 'ignore')


for u in ['https://www.shijuan1.com/sitemap.html',
          'https://www.shijuan1.com/sitemap.xml',
          'https://www.shijuan1.com/plus/search.php?kwtype=0&keyword=' + urllib.parse.quote('2023年高考数学')]:
    try:
        s, t = g(u)
        arts = re.findall(r'<a[^>]+href="(/a/sj[^"]+\.html)"[^>]*>\s*([^<]{4,80}?)\s*</a>', t)
        print(u, 'HTTP', s, '文章', len(arts))
        for a in arts[:5]:
            print('   ', a[0][:40], a[1])
    except Exception as e:
        print(u, 'ERR', type(e).__name__, str(e)[:80])
