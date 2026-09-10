"""对拍抽检流水线（项目书 §6 质量保障）。

流程：
1. 读取 data/question_bank.json 中 status=ready 的题目
2. 每道题让模型独立解 n 次（默认 3，--n 调整）
3. LLM-judge 将每次解答与官方参考答案对拍（一致/不一致/无法判断）
4. 汇总正确率与自洽一致性，输出 data/check_report.json

注意：所有调用同样受预算守卫限制（日限额 + 总预算 + 超支即停）。
用法（在 app 目录下）：
  python -m quality.run_check --n 3 --limit 10
"""
import argparse
import datetime as dt
import json
import sys

from tutor import client, config, prompts


def load_bank():
    if not config.QUESTION_BANK.exists():
        print("题库不存在：", config.QUESTION_BANK)
        sys.exit(1)
    return json.loads(config.QUESTION_BANK.read_text(encoding="utf-8"))


def save_report(report):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = config.DATA_DIR / "check_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告已保存：{out}")


def main():
    ap = argparse.ArgumentParser(description="对拍抽检流水线")
    ap.add_argument("--n", type=int, default=3, help="每题独立解答次数（默认 3）")
    ap.add_argument("--limit", type=int, default=0, help="只测前 N 道题（0=全部）")
    args = ap.parse_args()

    bank = load_bank()
    questions = [q for q in bank.get("questions", []) if q.get("status") == "ready"]
    if args.limit:
        questions = questions[: args.limit]
    if not questions:
        print("没有 status=ready 的题目。请先按 scripts/fetch_papers.md 采集真题，"
              "并把条目 status 置为 ready。")
        return

    print(f"共 {len(questions)} 道题，每题独立解 {args.n} 次。")
    report = {
        "checked_at": dt.datetime.now().isoformat(timespec="seconds"),
        "results": [],
    }

    for q in questions:
        answers = []
        for i in range(args.n):
            try:
                answers.append(client.chat(prompts.solve(q["question"])))
            except client.NoApiKeyError as e:
                print("ERROR:", e)
                sys.exit(1)
            except client.BudgetExceededError as e:
                print("WARNING:", e)
                print("预算耗尽，抽检提前停止（超支即停）。")
                save_report(report)
                sys.exit(1)

        verdicts = []
        for ans in answers:
            try:
                verdicts.append(client.chat(prompts.judge(ans, q["official_answer"])))
            except client.BudgetExceededError as e:
                print("WARNING:", e)
                save_report(report)
                sys.exit(1)

        ok_count = verdicts.count("一致")
        item = {
            "id": q["id"],
            "province": q.get("province"),
            "source_type": q.get("source_type"),
            "question": q["question"][:80],
            "correct_ratio": f"{ok_count}/{len(verdicts)}",
            "verdicts": verdicts,
            "answers": answers,
        }
        report["results"].append(item)
        tag = " · ".join(filter(None, [q.get("province"), q.get("source_type")]))
        print(f"[{q['id']}][{tag}] 对拍正确率 {item['correct_ratio']} ｜ {verdicts}")

    ok_total = sum(1 for r in report["results"] if "一致" in r["verdicts"])
    print(f"\n汇总：共 {len(report['results'])} 题，至少一次判定一致的题数 {ok_total}。")
    save_report(report)


if __name__ == "__main__":
    main()
