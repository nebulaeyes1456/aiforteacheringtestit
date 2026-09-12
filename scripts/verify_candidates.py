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
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # app/

from tutor import client, config, prompts

CANDIDATES = config.DATA_DIR / "candidates.json"
SOLVE_WORKERS = 5  # 每题 5 次独立解答并发执行


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


def normalize(s: str) -> str:
    """宽松归一化：去空白、统一标点，保留逗号等分隔符。"""
    s = (s or "").strip()
    s = s.replace("，", ",").replace("。", ".").replace("：", ":").replace("；", ";")
    return re.sub(r"\s+", "", s)


def solve_many(question: str, kind: str, n: int = SOLVE_WORKERS):
    """并发独立解答 n 次。返回 (结果列表, 是否预算耗尽)。"""
    def one(_):
        try:
            if kind == "free":
                return ("ok", client.chat(prompts.solve_final(question), temperature=0.2, max_tokens=64).strip())
            return ("ok", solve_letter(question).strip().upper())
        except client.NoApiKeyError:
            raise
        except client.BudgetExceededError as e:
            return ("err", str(e))
        except Exception as e:
            return ("err", f"{type(e).__name__}: {str(e)[:80]}")

    with ThreadPoolExecutor(max_workers=n) as ex:
        results = list(ex.map(one, range(n)))
    ok_vals = [v for s, v in results if s == "ok"]
    err_msgs = [v for s, v in results if s == "err"]
    return ok_vals, err_msgs


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
        kind = c.get("kind", "choice")
        print(f"[验证中] {qid}({kind}): {c['question'][:40]}…")
        try:
            raw, err_msgs = solve_many(c["question"], kind)
        except client.NoApiKeyError as e:
            print("ERROR:", e)
            sys.exit(1)
        if err_msgs:
            print(f"    WARNING: {len(err_msgs)} 次调用失败（{err_msgs[0][:80]}）")
            if any("预算" in m or "budget" in m.lower() for m in err_msgs):
                print("    预算耗尽，停止。")
                break

        official = (c.get("official_answer") or "").strip()
        if kind == "free":
            norm = [normalize(a) for a in raw]
            unanimous = len(norm) == n_solves and len(set(norm)) == 1
            final = norm[0] if unanimous else ""
            official_norm = normalize(official)
        else:
            letters = [a[0] for a in raw if a and a[0] in "ABCD"]
            unanimous = len(letters) == n_solves and len(set(letters)) == 1
            final = letters[0] if unanimous else ""
            official_norm = official.upper()

        note = "AI 独立解答 5 次一致；官方答案待人工核对"
        if unanimous and official_norm:
            if kind == "free":
                # 自由作答：表述形式多样，用 LLM 对拍判断实质一致
                try:
                    verdict = client.chat(prompts.judge(final, official)).strip()
                except (client.NoApiKeyError, client.BudgetExceededError) as e:
                    print("WARNING:", e)
                    verdict = "无法判断"
                if verdict == "一致":
                    note = "AI 独立解答 5 次一致，且与官方答案对拍一致"
                else:
                    print(f"    [WARN] 对拍判定 [{verdict}]：AI 共识 [{final}] vs 官方 [{official}]，拒绝入库")
                    log["rejected"].append({"id": qid, "raw": raw, "official": official})
                    continue
            else:
                if final == official_norm:
                    note = "AI 独立解答 5 次一致，且与官方答案一致"
                else:
                    print(f"    [WARN] AI 共识 [{final}] 与官方答案 [{official}] 不符，拒绝入库")
                    log["rejected"].append({"id": qid, "raw": raw, "official": official})
                    continue
        print(f"    5 次答案：{raw} → {'[PASS] 一致通过' if unanimous else '[REJECT] 不一致，拒绝入库'}")
        if not unanimous:
            log["rejected"].append({"id": qid, "raw": raw, "official": official})
            continue
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
                "subject": c.get("subject", "数学"),
                "question": c["question"],
                "official_answer": official_norm or final,
                "verify": note,
            }
        )
        log["verified"].append({"id": qid, "answer": official_norm or final, "raw": raw})

    bank_path.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")
    log["time"] = dt.datetime.now().isoformat(timespec="seconds")
    log_path = config.DATA_DIR / "verify_log.json"
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n入库 {len(log['verified'])} 道，拒绝 {len(log['rejected'])} 道。")
    print("验证记录：", log_path)
    print("预算状态：", client.budget_status())


if __name__ == "__main__":
    main()
