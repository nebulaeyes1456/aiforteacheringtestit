#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 7-zip 官网下载页解析最新 extra 包并下载"""
import os, re, ssl, urllib.request

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(APP, 'tools')
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.status, r.read()


s, body = get('https://www.7-zip.org/download.html')
print('download.html HTTP', s)
txt = body.decode('utf-8', 'ignore')
names = re.findall(r'href="(a/([0-9a-z.-]+extra\.7z))"', txt)
print('找到 extra 包:', names[:6])
if not names:
    print(txt[:800])
    raise SystemExit(1)
url = 'https://www.7-zip.org/' + names[0][0]
path = os.path.join(TOOLS, names[0][1])
print('下载:', url)
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=300, context=CTX) as r, open(path, 'wb') as f:
    while True:
        chunk = r.read(65536)
        if not chunk:
            break
        f.write(chunk)
print('完成:', path, os.path.getsize(path), 'bytes')
