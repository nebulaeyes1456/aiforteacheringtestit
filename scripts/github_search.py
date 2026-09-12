"""在服务器上搜索 GitHub 开源题库（境外服务器访问 GitHub 更稳）。

用法：python scripts/github_search.py [关键词...]
默认关键词：中考题库 / 高考题库 / 中学题库 / 试题库 json
"""
import json
import sys
import urllib.parse
import urllib.request

QUERIES = ["中考题库", "高考题库", "中学题库 json", "试题库 json", "exam question bank china"]


def search(q: str, per_page: int = 5):
    url = (
        "https://api.github.com/search/repositories?q="
        + urllib.parse.quote(q)
        + f"&per_page={per_page}&sort=stars"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "tutor-deploy-bot",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    queries = sys.argv[1:] or QUERIES
    for q in queries:
        print(f"===== {q} =====")
        try:
            data = search(q)
        except Exception as e:
            print("  搜索失败:", e)
            continue
        items = data.get("items", [])
        if not items:
            print("  （无结果）")
        for it in items:
            print(
                f"  {it['full_name']} | ⭐{it['stargazers_count']} | "
                f"{it.get('language')} | {(it.get('description') or '')[:80]}"
            )
        print()


if __name__ == "__main__":
    main()
