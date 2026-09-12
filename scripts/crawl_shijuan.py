#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第一试卷网历年试卷爬虫（遵守 robots：限速、只取公开下载链接）。

用法：
  python scripts/crawl_shijuan.py --col sjsxgk --years 2023,2024,2025 --max 15
  python scripts/crawl_shijuan.py --list-cols

流程：栏目列表分页 → 详情页 → rar 下载 → bsdtar 解压 → 清单存档 data/crawled_manifest.json
"""
import argparse
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request

BASE = 'https://www.shijuan1.com'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # app/
RAW = os.path.join(ROOT, 'data', 'raw')
MANIFEST = os.path.join(ROOT, 'data', 'crawled_manifest.json')

# 栏目：代码 -> (学科, 考试类型, 路径)
COLUMNS = {
    'sjsxgk': ('数学', '高考', '/a/sjsxgk/'),
    'sjsxzk': ('数学', '中考', '/a/sjsxzk/'),
    'sjwlgk': ('物理', '高考', '/a/sjwlgk/'),
    'sjwlzk': ('物理', '中考', '/a/sjwlzk/'),
    'sjhxgk': ('化学', '高考', '/a/sjhxgk/'),
    'sjhxzk': ('化学', '中考', '/a/sjhxzk/'),
    'sjywgk': ('语文', '高考', '/a/sjywgk/'),
    'sjywzk': ('语文', '中考', '/a/sjywzk/'),
    'sjyygk': ('英语', '高考', '/a/sjyygk/'),
    'sjyzzk': ('英语', '中考', '/a/sjyyzk/'),
    'sjswgk': ('生物', '高考', '/a/sjswgk/'),
    'sjlsgk': ('历史', '高考', '/a/sjlsgk/'),
    'sjdlgk': ('地理', '高考', '/a/sjdlgk/'),
    'sjzzgk': ('道法', '高考', '/a/sjzzgk/'),
}

# 学科主栏目：一页列出该科全部文章（历年真题都在这里）
SUBJECT_CODES = {'数学': 'sx', '物理': 'wl', '化学': 'hx', '英语': 'yy', '语文': 'yw',
                 '生物': 'sw', '历史': 'ls', '地理': 'dl', '道法': 'zz'}

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def get(url, timeout=30, referer=None, max_bytes=None):
    hdr = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36'}
    if referer:
        hdr['Referer'] = referer
    req = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.status, r.read(max_bytes) if max_bytes else r.read()


def fetch_html(url):
    s, body = get(url)
    for enc in ('gb18030', 'utf-8'):
        try:
            return body.decode(enc)
        except UnicodeDecodeError:
            continue
    return body.decode('gb18030', 'ignore')


def list_articles(col_path):
    """遍历栏目列表分页，返回 [(标题, 详情URL)]。"""
    articles = []
    page_urls = [BASE + col_path]
    for pageno in range(1, 200):
        if pageno > 1:
            page_urls.append(f'{BASE}{col_path}list_{pageno}.html')
    for pu in page_urls:
        try:
            txt = fetch_html(pu)
        except Exception as e:
            print(f'  分页获取失败 {pu}: {type(e).__name__}')
            break
        found = re.findall(r'<a[^>]+href="([^"]+\.html)"[^>]*>\s*(.{6,80}?)\s*</a>', txt, re.S)
        new = [(t.strip(), h if h.startswith('http') else BASE + h)
               for h, t in found if '/a/sj' in h and 'list_' not in h]
        if not new:
            break
        articles.extend(new)
        # 分页是否有下一页
        if f'list_{pageno + 1}' not in txt and f'index_{pageno + 1}' not in txt:
            break
        time.sleep(0.6)
    # 去重保序
    seen, out = set(), []
    for t, u in articles:
        if u not in seen:
            seen.add(u)
            out.append((t, u))
    return out


def year_of(title):
    m = re.search(r'(20\d{2})', title)
    return int(m.group(1)) if m else None


def detail_download_link(article_url):
    txt = fetch_html(article_url)
    m = re.search(r'href="([^"]+?\.(?:rar|zip|docx?|pdf))"', txt, re.I)
    if not m:
        return None
    u = m.group(1)
    return u if u.startswith('http') else BASE + u


def safe_name(s):
    s = re.sub(r'[\\/:*?"<>|]', '_', s).strip()[:80]
    return s or 'unnamed'


def extract_archive(archive_path, out_dir):
    """用系统 bsdtar（Windows 自带）解压 rar/zip。"""
    os.makedirs(out_dir, exist_ok=True)
    r = subprocess.run(['tar', '-xf', archive_path, '-C', out_dir],
                       capture_output=True, text=True)
    return r.returncode == 0


def load_manifest():
    if os.path.exists(MANIFEST):
        try:
            return json.load(open(MANIFEST, encoding='utf-8'))
        except json.JSONDecodeError:
            pass
    return {'papers': []}


def save_manifest(m):
    os.makedirs(RAW, exist_ok=True)
    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--col', default='')
    ap.add_argument('--subject', default='', help='学科名（数学/物理/化学/英语/语文/生物/历史/地理/道法），爬全科栏目')
    ap.add_argument('--exam', default='', help='只保留含该词的标题（如：高考/中考）')
    ap.add_argument('--years', default='2020,2021,2022,2023,2024,2025,2026')
    ap.add_argument('--max', type=int, default=0, help='0=不限量')
    ap.add_argument('--list-cols', action='store_true')
    args = ap.parse_args()

    if args.list_cols:
        for code, (subj, exam, path) in COLUMNS.items():
            print(code, subj, exam, path)
        return

    years = {int(y) for y in args.years.split(',') if y.strip().isdigit()}
    if args.subject and args.subject in SUBJECT_CODES:
        subj = args.subject
        exam = args.exam or '全部'
        col_path = '/a/sj' + SUBJECT_CODES[subj] + '/'
        tag = subj + exam
    else:
        subj, exam, col_path = COLUMNS.get(args.col, ('未知', '未知', '/' + args.col + '/'))
        tag = args.col
    print(f'== 栏目 {tag} 年份过滤 {sorted(years)}，最多 {args.max or "不限"} 份 ==')

    articles = list_articles(col_path)
    print(f'  列表共 {len(articles)} 篇')
    if args.exam:
        articles = [(t, u) for t, u in articles if args.exam in t]
        print(f'  按「{args.exam}」过滤后 {len(articles)} 篇')
    manifest = load_manifest()
    done_urls = {p['url'] for p in manifest['papers']}
    got = 0
    for title, url in articles:
        if args.max and got >= args.max:
            break
        y = year_of(title)
        if y not in years:
            continue
        if url in done_urls:
            print(f'  [跳过] {title}')
            continue
        print(f'  [{y}] {title}')
        time.sleep(0.5)
        try:
            dl = detail_download_link(url)
            if not dl:
                print('    [SKIP] 无下载链接')
                continue
            _, body = get(dl, timeout=180, referer=BASE + '/')
            ext = os.path.splitext(urllib.parse.urlparse(dl).path)[1] or '.rar'
            safe = safe_name(title)
            paper_dir = os.path.join(RAW, args.col, safe)
            archive = os.path.join(paper_dir, 'paper' + ext)
            os.makedirs(paper_dir, exist_ok=True)
            with open(archive, 'wb') as f:
                f.write(body)
            if not extract_archive(archive, paper_dir):
                print(f'    [FAIL] 解压失败，跳过（{archive}）')
                continue
            files = [n for n in os.listdir(paper_dir) if not n.startswith('paper.')]
            docs = [n for n in files if re.search(r'\.(docx?|pdf)$', n, re.I)]
            manifest['papers'].append({
                'title': title, 'url': url, 'year': y,
                'subject': subj, 'exam': exam, 'col': args.col or ('subject-' + args.subject),
                'dir': paper_dir.replace(ROOT + os.sep, ''),
                'docs': docs, 'files': files,
                'downloaded_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            })
            save_manifest(manifest)
            got += 1
            print(f'    [OK] 解压成功：{docs if docs else files}')
        except Exception as e:
            print(f'    [ERR] {type(e).__name__}: {str(e)[:100]}')
        time.sleep(0.8)
    print(f'== 完成：本次新增 {got} 份，累计 {len(manifest["papers"])} 份 ==')


if __name__ == '__main__':
    sys.exit(main())
