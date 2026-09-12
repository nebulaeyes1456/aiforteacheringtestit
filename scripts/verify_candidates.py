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

# 控制台/重定向输出统一 UTF-8，避免 GBK 编码崩溃
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # app/

from tutor import client, config, prompts

CANDIDATES = config.DATA_DIR / "candidates.json"
SOLVE_WORKERS = 5  # 每题 5 次独立解答并发执行


def solve_letter(question: str, subject: str = "数学"):
    return client.chat(
        [
            {
                "role": "system",
                "content": f"你是{subject}解题器。请解下面的选择题，只输出最终答案的选项字母（A/B/C/D 其中一个），"
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


BAD_ANSWER_RE = re.compile(
    r'题目不完整|题目缺失|信息不足|无法(判断|确定|求解)|缺少|不完整|题意不清|缺条件|条件不足|题干不全'
)


def solve_many(question: str, kind: str, subject: str = "数学", n: int = SOLVE_WORKERS):
    """并发独立解答 n 次。返回 (结果列表, 错误信息列表)。"""
    def one(_):
        try:
            if kind == "free":
                return ("ok", client.chat(prompts.solve_final(question, subject), temperature=0.2, max_tokens=64).strip())
            return ("ok", solve_letter(question, subject).strip().upper())
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
    log = {"verified": [], "rejected": [], "time": dt.datetime.now().isoformat(timespec="seconds")}
    log_path = config.DATA_DIR / "verify_log.json"
    # 跳过历史已拒绝的题（避免重跑反复花钱）
    if log_path.exists():
        try:
            old_log = json.loads(log_path.read_text(encoding="utf-8"))
            rejected_ids = {r["id"] for r in old_log.get("rejected", [])}
        except json.JSONDecodeError:
            rejected_ids = set()
    else:
        rejected_ids = set()

    def flush():
        bank_path.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    n_solves = 5
    processed = 0

    for c in cands:
        qid = c["id"]
        if qid in existing_ids:
            print(f"[跳过] {qid} 已存在")
            continue
        if qid in rejected_ids:
            print(f"[跳过] {qid} 历史已拒绝")
            continue
        kind = c.get("kind", "choice")
        print(f"[验证中] {qid}({kind}): {c['question'][:40]}…")
        # 空选项/选项相邻的残缺口：无需调用 AI，直接拒绝（省成本）
        if kind == "choice" and re.search(r'[A-D]\s*[.．、]\s*[A-D]\s*[.．、]', c['question']):
            print("    [REJECT] 选项残缺（公式图片化），拒绝入库")
            log["rejected"].append({"id": qid, "raw": [], "official": ""})
            continue
        try:
            raw, err_msgs = solve_many(c["question"], kind, c.get("subject", "数学"))
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
            # 残缺口拦截：AI 一致判定题目缺公式/条件 → 拒绝
            if unanimous and raw and BAD_ANSWER_RE.search(raw[0] or ""):
                print(f"    [REJECT] AI 判定题目残缺（{raw[0][:40]}），拒绝入库")
                log["rejected"].append({"id": qid, "raw": raw, "official": official})
                processed += 1
                if processed % 25 == 0:
                    flush()
                continue
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
                    verdict = client.chat(prompts.judge(final, official, c.get("subject", "数学"))).strip()
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
            processed += 1
            if processed % 25 == 0:
                flush()
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
        processed += 1
        if processed % 25 == 0:
            flush()

    bank_path.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")
    log["time"] = dt.datetime.now().isoformat(timespec="seconds")
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n入库 {len(log['verified'])} 道，拒绝 {len(log['rejected'])} 道。")
    print("验证记录：", log_path)
    print("预算状态：", client.budget_status())


if __name__ == "__main__":
    main()
