#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地探测国内试卷站点可达性与 robots 规则（遵守抓取礼仪，控制频次）"""
import re, ssl, time, urllib.parse, urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

SITES = [
    ('第一试卷网', 'https://www.shijuan1.com/'),
    ('360题库网', 'https://www.360tk.com/'),
    ('学科网', 'https://www.zxxk.com/'),
    ('菁优网', 'https://www.jyeoo.com/'),
    ('新课标第一网', 'https://www.xkb1.com/'),
    ('考试酷', 'https://www.examcoo.com/'),
    ('国家中小学智慧教育平台', 'https://basic.smartedu.cn/'),
    ('国家教育资源公共服务平台', 'https://www.eduyun.cn/'),
]


def get(url, timeout=15):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.geturl(), r.read(90000)
    except Exception as e:
        return None, None, f"{type(e).__name__}: {str(e)[:110]}"


for name, url in SITES:
    print(f"\n== {name}  {url}")
    s, final, body = get(url)
    if isinstance(body, str):
        print(f"  ERR {body}")
        continue
    print(f"  HTTP {s}  final={final}  len={len(body)}")
    txt = body.decode('utf-8', 'ignore')
    m = re.search(r'<title>(.*?)</title>', txt, re.S)
    if m:
        print(f"  title: {m.group(1).strip()[:80]}")
    links = re.findall(r'href="([^"]+?\.(?:docx?|pdf|zip))"', txt, re.I)
    print(f"  首页可下载文件链接数: {len(links)}")
    for l in links[:5]:
        print(f"    {l}")
    host = urllib.parse.urlparse(url).netloc
    got_robots = False
    for proto in ('https', 'http'):
        s2, _, rb = get(f"{proto}://{host}/robots.txt")
        if s2 == 200:
            rt = rb.decode('utf-8', 'ignore')
            dis = re.findall(r'^Disallow:\s*(.*)', rt, re.M)
            print(f"  robots({proto}): 规则 {len(dis)} 条, 示例: {[d.strip() for d in dis[:8]]}")
            got_robots = True
            break
    if not got_robots:
        print(f"  robots: 无")
    time.sleep(1.0)
