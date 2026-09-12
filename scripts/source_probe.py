#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""境外服务器探测：GitHub/HuggingFace 上 K12 题库数据集的可用性与许可"""
import json, ssl, time, urllib.parse, urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def get(url, timeout=20, headers=None, max_bytes=80000):
    req = urllib.request.Request(url, headers=headers or {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) K12Probe/1.0',
        'Accept': 'application/json,text/html,*/*'})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read(max_bytes)
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:100]}"


def gh_search(q, n=6):
    print(f"\n### GitHub: {q}")
    url = ('https://api.github.com/search/repositories?q=' +
           urllib.parse.quote(q) + f'&per_page={n}')
    s, b = get(url, headers={'User-Agent': 'K12Probe', 'Accept': 'application/vnd.github+json'})
    if s != 200:
        print(f"  HTTP {s} {str(b)[:120]}")
        return
    for it in json.loads(b).get('items', []):
        lic = (it.get('license') or {}).get('spdx_id') or '-'
        print(f"  {it['full_name']} | star={it['stargazers_count']} | {it.get('language')} | lic={lic}")
        print(f"      {(it.get('description') or '')[:110]}")


def hf_search(q, n=8, filter_kw=()):
    print(f"\n### HuggingFace: {q}")
    url = f'https://huggingface.co/api/datasets?search={urllib.parse.quote(q)}&limit={n}'
    s, b = get(url)
    if s != 200:
        print(f"  HTTP {s} {str(b)[:120]}")
        return
    for d in json.loads(b):
        did = d.get('id')
        print(f"  {did} | dl={d.get('downloads')} | likes={d.get('likes')}")
        if filter_kw and not any(k.lower() in (did or '').lower() for k in filter_kw):
            continue
        s2, b2 = get(f"https://huggingface.co/api/datasets/{did}")
        if s2 == 200:
            meta = json.loads(b2)
            card = meta.get('cardData') or {}
            lic = card.get('license') or '-'
            sib = [x.get('rfilename') for x in meta.get('siblings', [])][:12]
            print(f"      lic={lic} | tags={meta.get('tags')}")
            print(f"      files={sib}")
        time.sleep(0.4)


gh_search("EduData")
gh_search("K-12EduBench")
gh_search("LiveK12Bench")
gh_search("EXAMS benchmark")
gh_search("math exam dataset chinese")
hf_search("EduData", filter_kw=('edudata',))
hf_search("K-12EduBench", filter_kw=('edubench',))
hf_search("LiveK12Bench", filter_kw=('live', 'k12'))
hf_search("EXAMS", filter_kw=('exams',))
