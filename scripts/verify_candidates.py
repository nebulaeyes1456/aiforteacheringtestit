"""候选新题验证入库流程（用户要求：任何题目都要 AI 做一遍、验证一遍再入库）。

流程：
1. 读取 data/candidates.json（候选题目，含来源信息）
2. 每道题让 AI 独立解答 5 次，要求只输出选项字母
3. 5 次答案完全一致 → 验证通过，写入 data/question_bank.json（status=ready，
   official_answer=AI 共识答案，并注明"官方答案待人工核对"）
4. 不一致 → 拒绝入库，记录到 data/verify_log.json

用法：python scripts/verify_candidates.py
"""
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # app/

from tutor import client, config, prompts

CANDIDATES = config.DATA_DIR / "candidates.json"


def solve_letter(question: str):
    return client.chat(
        [
            {
                "role": "system",
                "content": "你是数学解题器。请解下面的选择题，只输出最终答案的选项字母（A/B/C/D 其中一个），"
                "不要输出任何其他内容。",
            },
            {"role": "user", "content": question},
        ],
        temperature=0.2,
        max_tokens=16,
    )


def main():
    if not CANDIDATES.exists():
        print("找不到候选题库：", CANDIDATES)
        sys.exit(1)
    cands = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    bank_path = config.QUESTION_BANK
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    existing_ids = {q["id"] for q in bank.get("questions", [])}
    log = {"verified": [], "rejected": []}
    n_solves = 5

    for c in cands:
        qid = c["id"]
        if qid in existing_ids:
            print(f"[跳过] {qid} 已存在")
            continue
        print(f"[验证中] {qid}: {c['question'][:40]}…")
        answers = []
        for i in range(n_solves):
            try:
                answers.append(solve_letter(c["question"]).strip().upper())
            except client.NoApiKeyError as e:
                print("ERROR:", e)
                sys.exit(1)
            except client.BudgetExceededError as e:
                print("WARNING:", e, "—— 预算耗尽，停止。")
                break
        letters = [a[0] for a in answers if a and a[0] in "ABCD"]
        unanimous = len(letters) == n_solves and len(set(letters)) == 1
        print(f"    5 次答案：{answers} → {'✅ 一致通过' if unanimous else '❌ 不一致，拒绝入库'}")
        if unanimous:
            bank["questions"].append(
                {
                    "id": qid,
                    "status": "ready",
                    "province": c["province"],
                    "source_type": c["source_type"],
                    "source": c["source"],
                    "year": c["year"],
                    "type": c["type"],
                    "difficulty": c["difficulty"],
                    "tags": c["tags"],
                    "question": c["question"],
                    "official_answer": letters[0],
                    "verify": "AI 独立解答 5 次结果一致；官方答案待人工核对",
                }
            )
            log["verified"].append({"id": qid, "answer": letters[0], "raw": answers})
        else:
            log["rejected"].append({"id": qid, "raw": answers})

    bank_path.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")
    log["time"] = dt.datetime.now().isoformat(timespec="seconds")
    log_path = config.DATA_DIR / "verify_log.json"
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n入库 {len(log['verified'])} 道，拒绝 {len(log['rejected'])} 道。")
    print("验证记录：", log_path)
    print("预算状态：", client.budget_status())


if __name__ == "__main__":
    main()
