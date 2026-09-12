#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器：核查官方 QQ-MM/LiveK12Bench 仓库许可与数据文件"""
import json, ssl, urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def get(url, timeout=25, headers=None):
    req = urllib.request.Request(url, headers=headers or {'User-Agent': 'K12Probe/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read(30000)
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:100]}"


s, b = get('https://api.github.com/repos/QQ-MM/LiveK12Bench',
           headers={'User-Agent': 'K12Probe', 'Accept': 'application/vnd.github+json'})
print('repo QQ-MM/LiveK12Bench HTTP', s)
if s == 200:
    j = json.loads(b)
    print('  default_branch:', j.get('default_branch'))
    print('  license:', (j.get('license') or {}).get('spdx_id'))
    print('  description:', (j.get('description') or '')[:150])
    br = j.get('default_branch') or 'main'
    s2, b2 = get(f'https://api.github.com/repos/QQ-MM/LiveK12Bench/git/trees/{br}?recursive=0',
                 headers={'User-Agent': 'K12Probe', 'Accept': 'application/vnd.github+json'})
    print('  tree HTTP', s2)
    if s2 == 200:
        for it in json.loads(b2).get('tree', []):
            print('   ', it.get('type'), it.get('path'), it.get('size', ''))
    s3, b3 = get(f'https://raw.githubusercontent.com/QQ-MM/LiveK12Bench/{br}/LICENSE')
    print('  LICENSE HTTP', s3)
    if s3 == 200:
        print(b3.decode('utf-8', 'ignore')[:600])
