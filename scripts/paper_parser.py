#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""试卷解析：把抓取的 docx 试卷切分成单题，分流为「文本完整」与「需 OCR」两类。

- 文本完整题（选项/题干无图片、无空选项）→ 追加到 data/candidates.json（待 AI 核验）
- 需 OCR 题（题干/选项含图片公式或图）→ 记录到 data/needs_ocr.json（留给 OCR 流水线）
- 答案卷（标题/文件名含 答案/解析/听力）→ 记录到 data/answer_docs.json（留给答案提取）

用法：python scripts/paper_parser.py [--limit N]
"""
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # app/
ROOT = Path(__file__).resolve().parent.parent

from tutor import config  # noqa: E402

import docx  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402

PRIMARY_RE = re.compile(r'小学|一年级|二年级|三年级|四年级|五年级|六年级')
CUT_RE = re.compile(r'^\s*(?:【?解|【?答|解析|解答|答案|分析|点评|听力原文)')


def convert_doc_to_docx(path: Path):
    """用本机 Word（COM）把老式 .doc 转成 .docx，返回新路径；失败返回 None。"""
    out = path.with_suffix('.docx')
    if out.exists() and out.stat().st_size > 5000:
        return out
    try:
        import win32com.client as win32
        word = win32.Dispatch('Word.Application')
        word.Visible = False
        try:
            d = word.Documents.Open(str(path), ReadOnly=True)
            d.SaveAs2(str(out), FileFormat=16)  # 16 = docx
            d.Close(False)
        finally:
            word.Quit()
        return out if out.exists() else None
    except Exception:
        return None

RAW = config.DATA_DIR / 'raw'
MANIFEST = config.DATA_DIR / 'crawled_manifest.json'
CANDIDATES = config.DATA_DIR / 'candidates.json'
NEEDS_OCR = config.DATA_DIR / 'needs_ocr.json'
ANSWER_DOCS = config.DATA_DIR / 'answer_docs.json'

QNUM_RE = re.compile(r'^\s*(\d{1,2})\s*[.．、]\s*')
OPTION_RE = re.compile(r'([A-D])\s*[.．、]\s*')
PAGE_RE = re.compile(r'第\s*\d+\s*页')
PROVINCES = set(config.PROVINCES)


def para_has_image(p):
    return bool(p._p.findall('.//' + qn('w:pict')) or p._p.findall('.//' + qn('w:drawing')))


def paper_meta(entry):
    """从标题/清单推断省份、年级、考试类型。"""
    title = entry.get('title', '')
    subject = entry.get('subject', '数学')
    exam = entry.get('exam') or ('中考' if '中考' in title else ('高考' if '高考' in title else ''))
    province = '通用'
    for p in sorted(PROVINCES, key=len, reverse=True):
        if p in title and p != '通用':
            province = p
            break
    if not province or province == '通用':
        for kw in ('全国', '新课标', '北京', '上海', '天津', '重庆', '浙江', '江苏', '广东', '山东'):
            if kw in title:
                province = kw
                break
    grade = '高三' if '高考' in title else ('初三' if '中考' in title else '通用')
    year = entry.get('year') or (re.search(r'(20\d{2})', title) and re.search(r'(20\d{2})', title).group(1)) or ''
    return title, subject, exam, province, grade, year


def split_questions(paras):
    """把段落序列切成题目列表。每题为 {'stem': [...], 'has_image': bool}"""
    questions = []
    cur = None
    for text, has_img in paras:
        m = QNUM_RE.match(text)
        if m and int(m.group(1)) <= 60:
            if cur:
                questions.append(cur)
            cur = {'stem': [re.sub(QNUM_RE, '', text, count=1).strip()], 'has_image': has_img}
        elif cur:
            if PAGE_RE.search(text) and len(text) < 20:
                continue
            cur['stem'].append(text.strip())
            cur['has_image'] = cur['has_image'] or has_img
        else:
            continue
    if cur:
        questions.append(cur)
    return questions


def build_question(stem_lines, meta, qid):
    title, subject, exam, province, grade, year = meta
    # 截断解析/答案段落（含解析版文档防污染）
    cut_idx = None
    for i, line in enumerate(stem_lines):
        if CUT_RE.match(line):
            cut_idx = i
            break
    if cut_idx is not None:
        stem_lines = stem_lines[:cut_idx]
    text = '\n'.join([l for l in stem_lines if l]).strip()
    # 兜底：任意位置出现答案解析标记 → 截断（防同段落内联答案）
    text = re.split(r'【?答[案】]|【?解[析】]|参考答案|答案详解', text)[0].strip()
    if not text or len(text) < 8:
        return None
    # 选项检测
    option_parts = []
    body_lines = []
    for line in stem_lines:
        if OPTION_RE.match(line):
            option_parts.append(line)
        elif option_parts:
            option_parts[-1] += ' ' + line
        else:
            body_lines.append(line)
    has_options = len(option_parts) >= 2
    if has_options:
        # 检查是否有空选项（公式被图片化）
        for op in option_parts:
            segs = OPTION_RE.split(op)
            for i in range(2, len(segs), 2):
                if not segs[i].strip():
                    return {'needs_ocr': True, 'reason': '空选项(公式图片)', 'text': text}
    # 图检测
    if re.search(r'如图|见图|图所示|图中', text) and not any('图' in l for l in []):
        pass  # 下面统一按 stem 图片标记
    kind = 'choice' if has_options else 'free'
    return {
        'needs_ocr': False,
        'kind': kind,
        'question': text,
        'subject': subject,
        'exam': exam,
        'province': province,
        'grade': grade,
        'year': year,
    }


def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            pass
    return default


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    limit = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == '--limit' else None
    manifest = load_json(MANIFEST, {'papers': []})
    cands = load_json(CANDIDATES, [])
    existing_q = {c['question'] for c in cands if isinstance(c, dict)}
    ocr_items = load_json(NEEDS_OCR, {'items': []})
    answer_docs = load_json(ANSWER_DOCS, {'docs': []})

    stat = {'papers': 0, 'parsed': 0, 'text_ok': 0, 'needs_ocr': 0, 'skipped_answer': 0, 'no_doc': 0, 'converted_doc': 0}
    ocr_seen = {(i['dir'], i['question_index']) for i in ocr_items['items']}
    for entry in manifest['papers']:
        if limit and stat['papers'] >= limit:
            break
        stat['papers'] += 1
        title, subject, exam, province, grade, year = paper_meta(entry)
        # 跳过小学卷（产品面向初高中）
        if PRIMARY_RE.search(title) and '高考' not in title and '中考' not in title:
            stat['skipped_answer'] += 1
            continue
        docs = entry.get('docs') or []
        if not docs:
            stat['no_doc'] += 1
            continue
        meta = (title, subject, exam, province, grade, year)
        # 区分试卷卷与答案卷
        paper_docs = [d for d in docs if not re.search(r'答案|解析|听力|听力材料', d)]
        ans_docs = [d for d in docs if re.search(r'答案|解析', d)]
        if not paper_docs:
            paper_docs = docs[:1]  # 只有一份文档时先当试卷
            ans_docs = []
        for ad in ans_docs:
            answer_docs['docs'].append({
                'dir': entry['dir'], 'file': ad, 'subject': subject, 'title': title, 'year': year
            })
        path = Path(ROOT) / entry['dir'] / paper_docs[0]
        if not path.exists():
            stat['no_doc'] += 1
            continue
        if path.suffix.lower() == '.doc':
            converted = convert_doc_to_docx(path)
            if converted is None:
                print(f"[ERR] .doc 转换失败：{path.name}")
                continue
            stat['converted_doc'] += 1
            path = converted
        try:
            d = docx.Document(str(path))
        except Exception as e:
            print(f"[ERR] 打不开 {path.name}: {type(e).__name__}")
            continue
        paras = [(p.text, para_has_image(p)) for p in d.paragraphs]
        questions = split_questions(paras)
        for qi, q in enumerate(questions):
            stat['parsed'] += 1
            res = build_question(q['stem'], meta, f"{entry.get('col','p')}-{entry.get('year','')}-{qi}")
            if res is None:
                continue
            if q['has_image'] or res.pop('needs_ocr', False):
                stat['needs_ocr'] += 1
                key = (entry['dir'], qi)
                if key not in ocr_seen:
                    ocr_seen.add(key)
                    ocr_items['items'].append({
                        'dir': entry['dir'], 'doc': paper_docs[0], 'title': title,
                        'subject': subject, 'year': year, 'text': (res.get('question') or res.get('text') or '')[:300],
                        'question_index': qi, 'flagged_at': dt.datetime.now().isoformat(timespec='seconds'),
                    })
                continue
            if res['question'] in existing_q:
                continue
            existing_q.add(res['question'])
            stat['text_ok'] += 1
            cands.append({
                'id': f"sj{res['year'] or 'xxxx'}-{stat['text_ok']:04d}",
                'kind': res['kind'],
                'question': res['question'],
                'province': res['province'],
                'source_type': '历年真题',
                'source': title[:60],
                'year': res['year'],
                'type': '选择题' if res['kind'] == 'choice' else '解答题',
                'difficulty': '中等',
                'tags': [],
                'subject': res['subject'],
                'official_answer': '',
            })

    save_json(CANDIDATES, cands)
    save_json(NEEDS_OCR, ocr_items)
    save_json(ANSWER_DOCS, answer_docs)
    print(f"试卷 {stat['papers']} 份 | 切出题目 {stat['parsed']} 道 | "
          f"文本完整 {stat['text_ok']} 道 | 需OCR {len(ocr_items['items'])} 道 | "
          f"答案卷 {len(answer_docs['docs'])} 份 | 跳过小学 {stat['skipped_answer']} | "
          f"doc转换 {stat['converted_doc']} | 无文档 {stat['no_doc']} 份")
    print(f"候选清单累计：{len(cands)} 道 → {CANDIDATES}")


if __name__ == '__main__':
    main()
