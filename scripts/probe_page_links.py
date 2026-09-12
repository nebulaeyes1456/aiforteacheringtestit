#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查看栏目页分页标记与文章链接总数"""
import re, ssl, urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def g(u):
    req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
    return urllib.request.urlopen(req, timeout=15, context=CTX).read().decode('gb18030', 'ignore')


t = g('https://www.shijuan1.com/a/sjwlgk/')
# 所有包含“页”的链接
pag = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]*(?:下一页|末页|页)[^<]*)</a>', t)
print('含“页”链接:', pag[:10])
# 所有 sj 开头链接
alls = re.findall(r'href="(/a/sj[^"]+)"', t)
print('sj 链接总数:', len(set(alls)))
# 常见 dede 分页: index.html 或者带参数
other = re.findall(r'href="([^"]*(?:list|index|page)[^"]*)"', t)
print('其它分页线索:', sorted(set(other))[:10])
