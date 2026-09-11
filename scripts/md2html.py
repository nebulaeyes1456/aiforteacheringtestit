"""把 docs/ 下的 Markdown 文档批量转换为手机友好的 HTML。

用法：python scripts/md2html.py
输出：docs/html/*.html + docs/html/index.html
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # app/
DOCS = ROOT.parent / "docs"                     # 项目根下的 docs/
OUT = DOCS / "html"

CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
       max-width: 760px; margin: 0 auto; padding: 16px; line-height: 1.75;
       color: #1f2329; background: #fff; font-size: 16px; }
h1 { font-size: 24px; border-bottom: 2px solid #e5e8ec; padding-bottom: 8px; }
h2 { font-size: 20px; margin-top: 28px; border-bottom: 1px solid #e5e8ec; padding-bottom: 6px; }
h3 { font-size: 17px; margin-top: 20px; }
table { border-collapse: collapse; width: 100%; display: block; overflow-x: auto; margin: 12px 0; }
th, td { border: 1px solid #d5d8dd; padding: 8px 10px; text-align: left; font-size: 14px; }
th { background: #f2f4f7; }
blockquote { border-left: 4px solid #2f6fed; background: #f4f7fd; margin: 12px 0;
             padding: 8px 14px; color: #4a5568; border-radius: 0 8px 8px 0; }
code { background: #f0f1f3; border-radius: 4px; padding: 1px 6px; font-size: 14px; }
pre { background: #f6f8fa; padding: 12px; border-radius: 8px; overflow-x: auto; }
pre code { background: none; padding: 0; }
hr { border: none; border-top: 1px solid #e5e8ec; margin: 20px 0; }
a { color: #2f6fed; }
li { margin: 4px 0; }
"""


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def render(md_text: str) -> str:
    lines = md_text.splitlines()
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if s.startswith("```"):
            j = i + 1
            while j < n and not lines[j].strip().startswith("```"):
                j += 1
            code_text = "\n".join(lines[i + 1:j])
            out.append(f"<pre><code>{html.escape(code_text)}</code></pre>")
            i = j + 1
            continue
        if s.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|?$", lines[i + 1].strip()):
            rows = []
            j = i
            while j < n and lines[j].strip().startswith("|"):
                cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                rows.append(cells)
                j += 1
            header, body = rows[0], rows[2:]
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead><tbody>")
            for r in body:
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            out.append("</tbody></table>")
            i = j
            continue
        if s.startswith("### "):
            out.append(f"<h3>{inline(s[4:])}</h3>")
        elif s.startswith("## "):
            out.append(f"<h2>{inline(s[3:])}</h2>")
        elif s.startswith("# "):
            out.append(f"<h1>{inline(s[2:])}</h1>")
        elif s == "---":
            out.append("<hr>")
        elif s.startswith("> "):
            out.append(f"<blockquote>{inline(s[2:])}</blockquote>")
        elif re.match(r"^\d+\.\s", s):
            items = [s]
            j = i + 1
            while j < n and re.match(r"^\d+\.\s", lines[j].strip()):
                items.append(lines[j].strip())
                j += 1
            out.append("<ol>" + "".join(f"<li>{inline(re.sub(r'^\\d+\\.\\s', '', t))}</li>" for t in items) + "</ol>")
            i = j
            continue
        elif s.startswith("- "):
            items = [s]
            j = i + 1
            while j < n and lines[j].strip().startswith("- "):
                items.append(lines[j].strip())
                j += 1
            out.append("<ul>" + "".join(f"<li>{inline(t[2:])}</li>" for t in items) + "</ul>")
            i = j
            continue
        else:
            para = [s]
            j = i + 1
            while j < n and lines[j].strip() and not re.match(r"^(#|>|- |\d+\.|\||---)", lines[j].strip()):
                para.append(lines[j].strip())
                j += 1
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            i = j
            continue
        i += 1
    return "\n".join(out)


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>
"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(DOCS.glob("*.md"))
    if not files:
        print("docs 目录下没有 md 文件")
        sys.exit(1)
    items = []
    for f in files:
        body = render(f.read_text(encoding="utf-8"))
        title = f.stem
        (OUT / f"{f.stem}.html").write_text(page(title, body), encoding="utf-8")
        items.append((f.stem, f.stem + ".html"))
        print("生成:", f.stem + ".html")

    index_body = "<h1>项目文档（手机版）</h1><ul>"
    for name, fn in items:
        index_body += f'<li><a href="{fn}">{html.escape(name)}</a></li>'
    index_body += "</ul>"
    (OUT / "index.html").write_text(page("项目文档索引", index_body), encoding="utf-8")
    print("生成: index.html")


if __name__ == "__main__":
    main()
