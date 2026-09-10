"""Web 服务（本地 MVP，项目书 §4）。

合规（§8）：匿名会话，session_id 为随机串，不收集任何身份信息；
埋点（§14 轮改进）：data/stats.json 记录会话/追问/解锁等脱敏事件计数。
"""
import datetime as dt
import json
import random
import uuid

from flask import Flask, jsonify, render_template, request

from tutor import client, config, engine

app = Flask(__name__)
SESSIONS = {}  # session_id -> engine.Session


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


@app.get("/sw.js")
def sw_js():
    """Service Worker 放在根路径，保证 scope 覆盖整个应用。"""
    return app.send_static_file("sw.js")


@app.get("/api/status")
def status():
    data = _load_users()
    u = data["users"].get(_uid()) or {"cost": 0.0}
    _, _, days_left = _window_status(data)
    return jsonify(
        {
            "budget": client.budget_status(),
            "active_sessions": len(SESSIONS),
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


@app.get("/api/provinces")
def provinces():
    return jsonify({"default": config.PROVINCE, "list": config.PROVINCES})


@app.get("/api/grades")
def grades():
    return jsonify({"default": config.GRADE, "list": config.GRADES})


@app.get("/api/practice")
def practice():
    """随机练一题：从题库抽 status=ready 的题，可按省份筛选。"""
    province = (request.args.get("province") or "").strip()
    if not config.QUESTION_BANK.exists():
        return jsonify({"error": "题库尚未建立，请先按 scripts/fetch_papers.md 采集题目。"}), 404
    try:
        bank = json.loads(config.QUESTION_BANK.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return jsonify({"error": "题库文件格式错误，请检查 data/question_bank.json。"}), 500
    pool = [q for q in bank.get("questions", []) if q.get("status") == "ready"]
    if province and province != "通用":
        pool = [q for q in pool if q.get("province") == province]
    if not pool:
        return jsonify({"error": f"题库中暂无可练的题（省份：{province or '不限'}）。"}), 404
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
                "question": q.get("question"),
            }
        }
    )


@app.post("/api/start")
def start():
    body = request.get_json(silent=True) or {}
    question = body.get("question", "")
    province = (body.get("province") or "").strip() or config.PROVINCE
    grade = (body.get("grade") or "").strip() or config.GRADE

    def run():
        _ensure_user(_uid())
        sid = uuid.uuid4().hex[:12]
        s = engine.Session(province, grade)
        result = s.start(question)
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

    def run():
        _ensure_user(_uid())
        result = s.reply(body.get("text", ""))
        _charge_user(_uid(), client.last_call_cost)
        _stat("student_reply")
        return jsonify(result)

    return _guard(run)


@app.post("/api/unlock")
def unlock():
    body = request.get_json(silent=True) or {}
    s = _get_session(body)
    if not s:
        return jsonify({"error": "会话不存在或已过期"}), 404

    def run():
        _ensure_user(_uid())
        text = s.unlock()
        _charge_user(_uid(), client.last_call_cost)
        _stat("unlock")
        return jsonify({"reply": text})

    return _guard(run)


@app.post("/api/similar")
def similar():
    body = request.get_json(silent=True) or {}
    s = _get_session(body)
    if not s:
        return jsonify({"error": "会话不存在或已过期"}), 404

    def run():
        _ensure_user(_uid())
        text = s.similar()
        _charge_user(_uid(), client.last_call_cost)
        _stat("similar")
        return jsonify({"reply": text})

    return _guard(run)


@app.post("/api/summarize")
def summarize():
    body = request.get_json(silent=True) or {}
    s = _get_session(body)
    if not s:
        return jsonify({"error": "会话不存在或已过期"}), 404

    def run():
        _ensure_user(_uid())
        text = s.summarize()
        _charge_user(_uid(), client.last_call_cost)
        _stat("summarize")
        return jsonify({"reply": text})

    return _guard(run)


if __name__ == "__main__":
    print("追问式讲题教练已启动：http://127.0.0.1:8000")
    print("预算状态：", client.budget_status())
    app.run(host="127.0.0.1", port=8000, debug=False)
