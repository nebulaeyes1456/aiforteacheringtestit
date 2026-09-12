"""讲题会话状态机（项目书 §4：引导 → 3 轮后可解锁完整讲解）。

- start：识别考点 + 第一步引导
- reply：判对错、错因、下一步引导（累计 MAX_GUIDE_ROUNDS 轮后可解锁）
- unlock / similar / summarize：完整讲解、变式题、掌握度小结
"""
from . import client, config, prompts

HELP_KEYWORDS = [
    "提示", "不会", "不懂", "怎么做", "帮帮我", "帮我", "卡住", "卡壳", "再讲",
    "不知道", "想不出", "没思路", "给点思路", "求思路", "怎么办", "不会做", "教教",
]


def _is_help_request(text: str) -> bool:
    """判断学生是在求助（要更深的提示）还是在作答。

    求助信号：包含常见求助词；或极短且不含数字/字母（如「嗯？」「太难」）。
    作答信号：含数字、字母、算式等实际内容（如「2」「x=3」「选B」）。
    """
    t = (text or "").strip()
    if any(k in t for k in HELP_KEYWORDS):
        return True
    compact = t.replace(" ", "")
    if len(compact) <= 3 and not any(ch.isdigit() or ch.isalpha() for ch in compact):
        return True
    return False


class Session:
    def __init__(self, province: str = "通用", grade: str = "通用", subject: str = "数学"):
        self.province = province
        self.grade = grade
        self.subject = subject
        self.question = None
        self.round = 0
        self.history = []  # ["教练：...", "学生：..."]
        self.state = "idle"  # idle / guiding / solved
        self.summary = None
        self.hint_stage = 0  # 同一题累计求助次数（升级提示用）

    def start(self, question: str) -> dict:
        question = (question or "").strip()
        if not question:
            raise ValueError("题目不能为空")
        if len(question) > 2000:
            raise ValueError("题目过长（>2000 字），请精简后重试")
        self.question = question
        self.round = 0
        self.history = []
        self.state = "guiding"
        self.hint_stage = 0
        reply = client.chat(prompts.guide_first(question, self.province, self.grade, self.subject))
        self.history.append("教练：" + reply)
        return {"reply": reply, "round": 0, "can_unlock": False}

    def reply(self, text: str) -> dict:
        if self.state != "guiding":
            raise ValueError("当前没有进行中的引导，请先开始讲题")
        text = (text or "").strip()
        if not text:
            raise ValueError("回答不能为空")
        self.round += 1
        self.history.append("学生：" + text)
        if _is_help_request(text):
            # 同一题再次求助：视为追问，给更深一步的提示
            self.hint_stage += 1
            reply = client.chat(
                prompts.guide_next(
                    self.question, self.history, self.hint_stage,
                    self.province, self.grade, self.subject,
                )
            )
        else:
            # 学生动手作答了：重置求助阶段，正常判错纠错
            self.hint_stage = 0
            reply = client.chat(
                prompts.feedback(
                    self.question, self.history, text,
                    self.province, self.grade, self.subject,
                )
            )
        self.history.append("教练：" + reply)
        return {
            "reply": reply,
            "round": self.round,
            "can_unlock": self.round >= config.MAX_GUIDE_ROUNDS,
        }

    def unlock(self) -> str:
        if not self.question:
            raise ValueError("会话未开始")
        reply = client.chat(prompts.full_solution(self.question, self.history, self.province, self.grade, self.subject))
        self.state = "solved"
        self.history.append("教练：" + reply)
        return reply

    def similar(self) -> str:
        if not self.question:
            raise ValueError("会话未开始")
        return client.chat(prompts.similar_question(self.question, self.history, self.province, self.grade, self.subject))

    def summarize(self) -> str:
        if not self.question:
            raise ValueError("会话未开始")
        reply = client.chat(prompts.summarize(self.question, self.history, self.province, self.grade, self.subject))
        self.summary = reply
        return reply
