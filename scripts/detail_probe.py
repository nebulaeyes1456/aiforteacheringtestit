#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地：抓第一试卷网详情页，提取下载链接并下载一个样本文件"""
import os, re, ssl, urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36'


def get(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Referer': 'https://www.shijuan1.com/'})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.status, r.read(400000)


page = 'https://www.shijuan1.com/a/sjwlgk/334040.html'
s, raw = get(page)
print('HTTP', s, 'len', len(raw))
txt = raw.decode('gb18030', 'ignore')
m = re.search(r'<title>(.*?)</title>', txt, re.S)
print('title:', m.group(1).strip() if m else '?')
links = re.findall(r'href="([^"]+?)"', txt)
dl = [l for l in links if re.search(r'\.(docx?|pdf|zip|rar)', l, re.I)]
print('下载链接:', dl[:10])
if dl:
    u = dl[0]
    if u.startswith('/'):
        u = 'https://www.shijuan1.com' + u
    s2, raw2 = get(u)
    print('下载 HTTP', s2, 'len', len(raw2))
    if s2 == 200 and len(raw2) > 1000:
        fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_dl.bin')
        with open(fn, 'wb') as f:
            f.write(raw2)
        print('已存 sample_dl.bin, magic:', raw2[:8].hex())
        if raw2[:4] == b'PK\x03\x04':
            print('类型: docx/zip (OOXML)')
        elif raw2[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
            print('类型: 老式二进制 .doc (OLE2)')
        elif raw2[:5] == b'%PDF-':
            print('类型: PDF')
