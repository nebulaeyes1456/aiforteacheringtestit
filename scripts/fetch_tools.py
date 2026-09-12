#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""准备抓取工具链：下载样本 rar + 便携 7z 解压器（无需安装、无需管理员）"""
import os, ssl, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))          # app/scripts
APP = os.path.dirname(BASE)                                 # app
RAW = os.path.join(APP, 'data', 'raw')
TOOLS = os.path.join(APP, 'tools')
os.makedirs(RAW, exist_ok=True)
os.makedirs(TOOLS, exist_ok=True)

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def download(url, path, referer=None):
    hdr = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0'}
    if referer:
        hdr['Referer'] = referer
    req = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(req, timeout=180, context=CTX) as r, open(path, 'wb') as f:
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)
    return os.path.getsize(path)


jobs = [
    ('https://www.shijuan1.com/uploads/soft/sj2025/wuli/gaokao/1-260210164645.rar',
     os.path.join(RAW, 'sample_wuli2025_cq.rar'), 'https://www.shijuan1.com/'),
    ('https://www.7-zip.org/a/7zr.exe', os.path.join(TOOLS, '7zr.exe'), None),
    ('https://www.7-zip.org/a/7z2409-extra.7z', os.path.join(TOOLS, '7z2409-extra.7z'), None),
]
for url, path, ref in jobs:
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        print('已存在, 跳过:', os.path.basename(path))
        continue
    try:
        n = download(url, path, ref)
        print('下载完成:', os.path.basename(path), n, 'bytes')
    except Exception as e:
        print('下载失败:', os.path.basename(path), type(e).__name__, str(e)[:120])
