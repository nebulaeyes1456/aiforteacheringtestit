"""讲题会话状态机（项目书 §4：引导 → 3 轮后可解锁完整讲解）。

- start：识别考点 + 第一步引导
- reply：判对错、错因、下一步引导（累计 MAX_GUIDE_ROUNDS 轮后可解锁）
- unlock / similar / summarize：完整讲解、变式题、掌握度小结
"""
from . import client, config, prompts


class Session:
    def __init__(self, province: str = "通用", grade: str = "通用"):
        self.province = province
        self.grade = grade
        self.question = None
        self.round = 0
        self.history = []  # ["教练：...", "学生：..."]
        self.state = "idle"  # idle / guiding / solved
        self.summary = None

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
        reply = client.chat(prompts.guide_first(question, self.province, self.grade))
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
        reply = client.chat(prompts.feedback(self.question, self.history, text, self.province, self.grade))
        self.history.append("教练：" + reply)
        return {
            "reply": reply,
            "round": self.round,
            "can_unlock": self.round >= config.MAX_GUIDE_ROUNDS,
        }

    def unlock(self) -> str:
        if not self.question:
            raise ValueError("会话未开始")
        reply = client.chat(prompts.full_solution(self.question, self.history, self.province, self.grade))
        self.state = "solved"
        self.history.append("教练：" + reply)
        return reply

    def similar(self) -> str:
        if not self.question:
            raise ValueError("会话未开始")
        return client.chat(prompts.similar_question(self.question, self.history, self.province, self.grade))

    def summarize(self) -> str:
        if not self.question:
            raise ValueError("会话未开始")
        reply = client.chat(prompts.summarize(self.question, self.history, self.province, self.grade))
        self.summary = reply
        return reply
