#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 docx 中图片的嵌入方式与位置，并导出 media 文件"""
import os, re, zipfile
import docx
from docx.oxml.ns import qn

SRC = r'C:\Users\31878\Documents\K12-AI-Tutor\app\data\raw\wuli2025_cq\2025年高考物理试卷（重庆卷）.docx'
OUT = r'C:\Users\31878\Documents\K12-AI-Tutor\app\data\raw\wuli2025_cq\media'
os.makedirs(OUT, exist_ok=True)

d = docx.Document(SRC)
body = d.element.body

# 遍历 body 的直接子元素，重建线性序列
seq = []
for child in body.iterchildren():
    tag = child.tag.split('}')[-1]
    if tag == 'p':
        paras = child.findall('.//' + qn('w:t'))
        text = ''.join(t.text or '' for t in paras)
        # 找段落中的图片
        imgs = child.findall('.//' + qn('a:blip'))
        drawings = child.findall('.//' + qn('w:drawing'))
        pics = child.findall('.//' + qn('w:pict'))
        seq.append(('P', text, len(drawings), len(pics)))
    elif tag == 'tbl':
        seq.append(('TBL', '', 0, 0))

print('顶层元素:', len(seq), ' 其中含图段落:', sum(1 for s in seq if s[2] or s[3]))
for s in seq[:15]:
    print(f"  [{s[0]}] text={s[1][:50]!r} drawings={s[2]} pict={s[3]}")

# 导出 media
with zipfile.ZipFile(SRC) as z:
    media = [n for n in z.namelist() if n.startswith('word/media/') and not n.endswith('/')]
    print('\nmedia 文件数:', len(media))
    for n in media:
        fn = os.path.join(OUT, os.path.basename(n))
        with open(fn, 'wb') as f:
            f.write(z.read(n))
    print('已导出到', OUT)

# 打印一个含图段落的 XML 片段
from lxml import etree
for child in body.iterchildren():
    tag = child.tag.split('}')[-1]
    if tag != 'p':
        continue
    if child.findall('.//' + qn('w:pict')) or child.findall('.//' + qn('w:drawing')):
        xml = etree.tostring(child, pretty_print=True).decode('utf-8')
        print('\n===== 含图段落 XML 片段 =====')
        print(xml[:2200])
        break

# 统计 rId -> 图片映射
rels = d.part.rels
img_rels = {rid: rel.target_ref for rid, rel in rels.items() if 'image' in rel.reltype}
print('图片关系数:', len(img_rels))
