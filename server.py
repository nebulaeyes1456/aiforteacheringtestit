"""Web 服务（本地 MVP，项目书 §4）。

合规（§8）：匿名会话，session_id 为随机串，不收集任何身份信息；
埋点（§14 轮改进）：data/stats.json 记录会话/追问/解锁等脱敏事件计数。
"""
import datetime as dt
import json
import random
import time
import uuid

from flask import Flask, jsonify, render_template, request

from tutor import client, config, engine, prompts

app = Flask(__name__)
SESSIONS = {}  # session_id -> engine.Session
SESSION_META = {}  # session_id -> {"key": 兑换码, "last": 上次活动时间}


# ---------- 内测成本控制（每人限额 + 人数上限） ----------

def _uid() -> str:
    return (request.headers.get("X-Tutor-Uid") or "").strip()


def _load_users():
    if config.USER_USAGE_FILE.exists():
        try:
            return json.loads(config.USER_USAGE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"users": {}}


def _save_users(data):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.USER_USAGE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _window_status(data: dict):
    """内测窗口：从第一个用户注册时刻起 14 天。返回 (start, end, days_left)。"""
    users = data.get("users", {})
    if not users:
        return None, None, None
    first = min(u.get("first_seen", "") for u in users.values() if u.get("first_seen"))
    try:
        start = dt.datetime.fromisoformat(first)
    except ValueError:
        return None, None, None
    end = start + dt.timedelta(days=config.BETA_DURATION_DAYS)
    days_left = max((end - dt.datetime.now()).days, 0)
    return start, end, days_left


def _ensure_user(uid: str):
    """新用户登记（超人数上限拒绝）；检查内测窗口与个人额度（超限拒绝）。"""
    if not uid:
        return None  # 无客户端 ID 时不做个人限额（兼容旧页面）
    data = _load_users()
    start, end, days_left = _window_status(data)
    if start is not None and days_left <= 0:
        raise ValueError(
            f"本次内测已结束（为期 {config.BETA_DURATION_DAYS} 天），感谢参与，正式版敬请期待。"
        )
    u = data["users"].get(uid)
    if not u:
        if len(data["users"]) >= config.BETA_MAX_USERS:
            raise ValueError(f"内测名额已满（上限 {config.BETA_MAX_USERS} 人），感谢关注。")
        u = data["users"][uid] = {
            "first_seen": dt.datetime.now().isoformat(timespec="seconds"),
            "cost": 0.0,
            "calls": 0,
        }
        _save_users(data)
    if u.get("cost", 0.0) >= config.BETA_USER_CAP_YUAN:
        raise ValueError(
            f"您的内测额度已用完（每人 ¥{config.BETA_USER_CAP_YUAN}），欢迎正式版再来。"
        )
    return u


def _charge_user(uid: str, cost: float):
    if not uid or not cost:
        return
    data = _load_users()
    u = data["users"].get(uid)
    if u:
        u["cost"] = round(u.get("cost", 0.0) + cost, 6)
        u["calls"] = u.get("calls", 0) + 1
        _save_users(data)


# ---------- 兑换码按时长计费（匿名密钥，不关联任何身份信息） ----------

def _key() -> str:
    return (request.headers.get("X-Tutor-Key") or "").strip().upper()


def _load_vouchers():
    if config.VOUCHER_FILE.exists():
        try:
            return json.loads(config.VOUCHER_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"vouchers": {}}


def _save_vouchers(data):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.VOUCHER_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _get_voucher(key: str):
    if not key:
        return None
    return _load_vouchers().get("vouchers", {}).get(key)


def _voucher_remaining(v) -> float:
    """剩余秒数。"""
    return max(round(v.get("hours", 0.0) * 3600 - v.get("seconds_used", 0.0), 1), 0.0)


def _check_voucher(v):
    if not v:
        return None
    if v.get("status") != "active":
        raise ValueError("兑换码已停用（已退款或作废），请联系卖家。")
    if _voucher_remaining(v) <= 0:
        raise ValueError("兑换时长已用完，可联系卖家续购或退款。")
    return v


def _pre_check(sid: str):
    """调用前检查：密钥用户查时长余额；否则按内测规则检查。"""
    meta = SESSION_META.get(sid)
    if meta:
        _check_voucher(_get_voucher(meta["key"]))
    else:
        _ensure_user(_uid())


def _after_call(sid: str):
    """密钥用户：按两次交互间的实际经过时间扣时长，挂机超过上限的部分不计费。"""
    meta = SESSION_META.get(sid)
    if not meta:
        return
    now = time.time()
    delta = min(now - meta["last"], config.VOUCHER_IDLE_CAP_SEC)
    meta["last"] = now
    if delta <= 0:
        return
    data = _load_vouchers()
    v = data["vouchers"].get(meta["key"])
    if v:
        v["seconds_used"] = round(v.get("seconds_used", 0.0) + delta, 1)
        _save_vouchers(data)


def _post_call(sid: str):
    """调用后结算：密钥用户扣时长；内测用户按 API 成本记账。"""
    if SESSION_META.get(sid):
        _after_call(sid)
    else:
        _charge_user(_uid(), client.last_call_cost)


def _stat(event: str):
    path = config.STATS_FILE
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data[event] = data.get(event, 0) + 1
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_session(body: dict):
    sid = (body or {}).get("session_id")
    s = SESSIONS.get(sid)
    if not s:
        return None
    return s


def _guard(fn):
    """统一异常处理：预算/密钥错误返回友好信息。"""
    try:
        return fn()
    except (client.NoApiKeyError, client.BudgetExceededError) as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/favicon.ico")
def favicon():
    """浏览器默认请求 /favicon.ico，返回图标避免 404。"""
    return app.send_static_file("icon.svg")


@app.get("/api/status")
def status():
    data = _load_users()
    u = data["users"].get(_uid()) or {"cost": 0.0}
    _, _, days_left = _window_status(data)
    v = _get_voucher(_key())
    voucher = None
    if v:
        voucher = {
            "hours": v.get("hours"),
            "remaining_hours": round(_voucher_remaining(v) / 3600, 2),
            "status": v.get("status"),
        }
    return jsonify(
        {
            "budget": client.budget_status(),
            "active_sessions": len(SESSIONS),
            "mode": config.ACCESS_MODE,
            "voucher": voucher,
            "user": {
                "spent": round(u.get("cost", 0.0), 4),
                "cap": config.BETA_USER_CAP_YUAN,
                "remaining": round(max(config.BETA_USER_CAP_YUAN - u.get("cost", 0.0), 0.0), 4),
                "users": len(data["users"]),
                "max_users": config.BETA_MAX_USERS,
                "window": {
                    "days_left": days_left,
                    "total_days": config.BETA_DURATION_DAYS,
                },
            },
        }
    )


@app.post("/api/redeem")
def redeem():
    """兑换码验证（不消耗任何时长）。"""
    body = request.get_json(silent=True) or {}
    key = (body.get("key") or "").strip().upper()
    v = _get_voucher(key)
    if not v:
        return jsonify({"error": "兑换码无效，请检查后重试。"}), 404
    if v.get("status") != "active":
        return jsonify({"error": "兑换码已停用（已退款或作废），请联系卖家。"}), 404
    return jsonify(
        {
            "ok": True,
            "hours": v.get("hours"),
            "remaining_hours": round(_voucher_remaining(v) / 3600, 2),
        }
    )


@app.get("/api/provinces")
def provinces():
    return jsonify({"default": config.PROVINCE, "list": config.PROVINCES})


@app.get("/api/grades")
def grades():
    return jsonify({"default": config.GRADE, "list": config.GRADES})


@app.get("/api/subjects")
def subjects():
    return jsonify({"default": config.SUBJECT, "list": config.SUBJECTS})


@app.get("/api/practice")
def practice():
    """随机练一题：从题库抽 status=ready 的题，可按省份与知识点关键词筛选；skip=1 时仅记录跳题埋点。"""
    province = (request.args.get("province") or "").strip()
    tag = (request.args.get("tag") or "").strip()
    subject = (request.args.get("subject") or "").strip()
    if request.args.get("skip") == "1":
        _stat("skip_question")
    if not config.QUESTION_BANK.exists():
        return jsonify({"error": "题库尚未建立，请先按 scripts/fetch_papers.md 采集题目。"}), 404
    try:
        bank = json.loads(config.QUESTION_BANK.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return jsonify({"error": "题库文件格式错误，请检查 data/question_bank.json。"}), 500
    pool = [q for q in bank.get("questions", []) if q.get("status") == "ready"]
    if province and province != "通用":
        pool = [q for q in pool if q.get("province") == province]
    if tag:
        pool = [q for q in pool if any(tag in (t or "") for t in (q.get("tags") or []))]
    if subject:
        pool = [q for q in pool if q.get("subject", "数学") == subject]
    if not pool:
        if subject and not any(q.get("subject") == subject for q in bank.get("questions", [])):
            return jsonify(
                {"error": f"「{subject}」题库正在建设中，先试试数学吧；其他学科题目会陆续上线。"}
            ), 404
        return jsonify(
            {
                "error": f"题库中暂无可练的题（学科：{subject or '不限'}，省份：{province or '不限'}，知识点：{tag or '不限'}）。"
            }
        ), 404
    q = random.choice(pool)
    # 只返回学生可见字段，不返回 official_answer
    return jsonify(
        {
            "question": {
                "id": q.get("id"),
                "province": q.get("province"),
                "source_type": q.get("source_type"),
                "year": q.get("year"),
                "type": q.get("type"),
                "difficulty": q.get("difficulty"),
                "tags": q.get("tags", []),
                "question": q.get("question"),
            }
        }
    )


@app.get("/api/tags")
def tags():
    """题库里所有知识点标签（去重排序），可按学科过滤，供前端联想输入。"""
    if not config.QUESTION_BANK.exists():
        return jsonify({"list": []})
    subject = (request.args.get("subject") or "").strip()
    try:
        bank = json.loads(config.QUESTION_BANK.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return jsonify({"list": []})
    tag_set = {
        t
        for q in bank.get("questions", [])
        if (not subject or q.get("subject", "数学") == subject)
        for t in (q.get("tags") or [])
        if t
    }
    return jsonify({"list": sorted(tag_set)})


@app.post("/api/summary_kp")
def summary_kp():
    """知识点要点总结（独立调用）：同样经过内测额度 / 兑换码计费。"""
    body = request.get_json(silent=True) or {}
    topic = (body.get("topic") or "").strip()
    province = (body.get("province") or "").strip() or config.PROVINCE
    grade = (body.get("grade") or "").strip() or config.GRADE
    subject = (body.get("subject") or "").strip() or config.SUBJECT
    if not topic:
        return jsonify({"error": "请先输入知识点关键词。"}), 400

    def run():
        v = _get_voucher(_key())
        if v:
            _check_voucher(v)
        else:
            if config.ACCESS_MODE == "private":
                raise ValueError("本服务仅限已购用户使用，请先输入兑换码。")
            _ensure_user(_uid())
        t0 = time.time()
        text = client.chat(prompts.knowledge_summary(topic, province, grade, subject))
        elapsed = time.time() - t0
        if v:
            data = _load_vouchers()
            vv = data["vouchers"].get(_key())
            if vv:
                vv["seconds_used"] = round(
                    vv.get("seconds_used", 0.0) + min(elapsed, config.VOUCHER_IDLE_CAP_SEC), 1
                )
                _save_vouchers(data)
        else:
            _charge_user(_uid(), client.last_call_cost)
        _stat("summary_kp")
        return jsonify({"reply": text})

    return _guard(run)


@app.post("/api/start")
def start():
    body = request.get_json(silent=True) or {}
    question = body.get("question", "")
    province = (body.get("province") or "").strip() or config.PROVINCE
    grade = (body.get("grade") or "").strip() or config.GRADE
    subject = (body.get("subject") or "").strip() or config.SUBJECT

    def run():
        sid = uuid.uuid4().hex[:12]
        v = _get_voucher(_key())
        if v:
            _check_voucher(v)
        else:
            if config.ACCESS_MODE == "private":
                raise ValueError("本服务仅限已购用户使用，请先输入兑换码。")
            _ensure_user(_uid())
        s = engine.Session(province, grade, subject)
        result = s.start(question)
        if v:
            SESSION_META[sid] = {"key": _key(), "last": time.time()}
        else:
            _charge_user(_uid(), client.last_call_cost)
        SESSIONS[sid] = s
        _stat("session_start")
        result["session_id"] = sid
        result["user_cost"] = client.last_call_cost
        return jsonify(result)

    return _guard(run)


@app.post("/api/reply")
def reply():
    body = request.get_json(silent=True) or {}
    s = _get_session(body)
    if not s:
        return jsonify({"error": "会话不存在或已过期"}), 404
    sid = body.get("session_id")

    def run():
        _pre_check(sid)
        result = s.reply(body.get("text", ""))
        _post_call(sid)
        _stat("student_reply")
        return jsonify(result)

    return _guard(run)


@app.post("/api/unlock")
def unlock():
    body = request.get_json(silent=True) or {}
    s = _get_session(body)
    if not s:
        return jsonify({"error": "会话不存在或已过期"}), 404
    sid = body.get("session_id")

    def run():
        _pre_check(sid)
        text = s.unlock()
        _post_call(sid)
        _stat("unlock")
        return jsonify({"reply": text})

    return _guard(run)


@app.post("/api/similar")
def similar():
    body = request.get_json(silent=True) or {}
    s = _get_session(body)
    if not s:
        return jsonify({"error": "会话不存在或已过期"}), 404
    sid = body.get("session_id")

    def run():
        _pre_check(sid)
        text = s.similar()
        _post_call(sid)
        _stat("similar")
        return jsonify({"reply": text})

    return _guard(run)


@app.post("/api/summarize")
def summarize():
    body = request.get_json(silent=True) or {}
    s = _get_session(body)
    if not s:
        return jsonify({"error": "会话不存在或已过期"}), 404
    sid = body.get("session_id")

    def run():
        _pre_check(sid)
        text = s.summarize()
        _post_call(sid)
        _stat("summarize")
        return jsonify({"reply": text})

    return _guard(run)


if __name__ == "__main__":
    print("追问式讲题教练已启动：http://127.0.0.1:8000")
    print("预算状态：", client.budget_status())
    app.run(host="127.0.0.1", port=8000, debug=False)
