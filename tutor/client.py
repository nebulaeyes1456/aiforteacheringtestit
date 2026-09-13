"""DeepSeek（OpenAI 兼容）客户端封装 + 预算守卫（项目书 §5 控费机制）。

- 每次调用记账到 data/usage.json（按官方返回的 token 用量估算成本）
- 日限额（TUTOR_DAILY_CAP）与总预算（TUTOR_API_BUDGET）双闸门
- 超支即停：达到上限后拒绝新调用，进入止损评审
"""
import datetime as dt
import json
import os
import threading

import requests

from . import config


class NoApiKeyError(Exception):
    """未配置 API Key。"""


class BudgetExceededError(Exception):
    """预算已用尽（总预算或当日限额）。"""


last_call_cost = 0.0  # 最近一次调用的实际成本（供上层按用户记账）

_ledger_lock = threading.Lock()
LEDGER_FILE = config.DATA_DIR / "usage_append.jsonl"  # 追加式流水账（权威）


def _today() -> str:
    return dt.date.today().isoformat()


def _load_legacy():
    """兼容旧版 usage.json。"""
    if config.USAGE_FILE.exists():
        try:
            return json.loads(config.USAGE_FILE.read_text(encoding="utf-8")).get("records", [])
        except json.JSONDecodeError:
            pass
    return []


def _load_ledger():
    records = _load_legacy()
    if LEDGER_FILE.exists():
        try:
            for line in LEDGER_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records


def _save_usage(data):
    """追加最新一条记录到 jsonl（线程安全，避免并发写丢账）。"""
    new_record = data["records"][-1] if data.get("records") else None
    if not new_record:
        return
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _ledger_lock:
        with open(LEDGER_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(new_record, ensure_ascii=False) + "\n")


def _cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (
        prompt_tokens * config.PRICE_INPUT
        + completion_tokens * config.PRICE_OUTPUT
    ) / 1_000_000


def total_spent() -> float:
    return sum(r.get("cost", 0.0) for r in _load_ledger())


def spent_today() -> float:
    return sum(
        r.get("cost", 0.0)
        for r in _load_ledger()
        if r.get("date") == _today()
    )


def budget_status() -> dict:
    total = total_spent()
    return {
        "total_spent": round(total, 4),
        "budget": config.API_BUDGET_YUAN,
        "remaining": round(config.API_BUDGET_YUAN - total, 4),
        "spent_today": round(spent_today(), 4),
        "daily_cap": config.DAILY_CAP_YUAN,
    }


def _check_budget():
    today = spent_today()
    total = total_spent()
    if today >= config.DAILY_CAP_YUAN:
        raise BudgetExceededError(
            f"今日限额 {config.DAILY_CAP_YUAN} 元已用完（今日已用 {today:.4f} 元），明日再试。"
        )
    if total >= config.API_BUDGET_YUAN:
        raise BudgetExceededError(
            f"总预算 {config.API_BUDGET_YUAN} 元已用完（累计 {total:.4f} 元），"
            "按项目书进入止损评审。"
        )


def chat(messages: list, max_tokens=None, temperature=None) -> str:
    """调用一次模型并记账。异常：NoApiKeyError / BudgetExceededError / requests 错误。"""
    key = os.environ.get(config.API_KEY_ENV)
    if not key:
        raise NoApiKeyError(
            f"未配置 API Key：请设置环境变量 {config.API_KEY_ENV}（见 README 快速开始）。"
        )
    _check_budget()

    payload = {
        "model": config.MODEL,
        "messages": messages,
        "stream": False,
        "max_tokens": max_tokens or config.MAX_TOKENS,
        "temperature": temperature if temperature is not None else config.TEMPERATURE,
    }
    resp = requests.post(
        f"{config.API_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    if resp.status_code == 401:
        raise NoApiKeyError("API Key 无效（401），请检查环境变量中的密钥。")
    resp.raise_for_status()
    body = resp.json()
    usage = body.get("usage") or {}
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    cost = _cost(prompt_tokens, completion_tokens)

    global last_call_cost
    last_call_cost = round(cost, 6)

    record = {
        "date": _today(),
        "time": dt.datetime.now().isoformat(timespec="seconds"),
        "model": config.MODEL,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost": round(cost, 6),
    }
    _save_usage({"records": [record]})

    return body["choices"][0]["message"]["content"]
