"""批量测试讲题效果（项目书 §6/§7），学生可用两种方式模拟：

- llm（默认，≤100 轮推荐）：用大模型扮演学生，画像由 8 个维度随机组合生成，
  刻意避免刻板印象（水平/性格/注意力/表达/状态/动机自由组合）。
- script（极大量测试用）：脚本行为模板，学生端不调用 LLM，更省钱。

每个会话流程：开始讲题 → N 轮追问 → 解锁完整讲解 → 掌握度小结；
会话结束后用一次 LLM 调用评估完整对话（5 维度 1-5 分 + 一句话总结），即「每次总结经验」。
结果写入 data/test_report.json 与 data/test_summaries.md。

用法（在 app 目录下）：
  python test_student.py --sessions 1 --rounds 3                 # 试跑（LLM 学生）
  python test_student.py --sessions 10 --rounds 8                # 80 轮学生发言（≤100 轮）
  python test_student.py --sessions 50 --rounds 5 --student script   # 极大量测试（省钱）
"""
import argparse
import datetime as dt
import json
import random

from tutor import client, config, engine, prompts

FALLBACK_QUESTIONS = [
    "已知关于 x 的一元二次方程 x^2 - 2(k-1)x + k^2 = 0 有两个不相等的实数根，求 k 的取值范围。",
    "已知抛物线 y = ax^2 + bx + 3 经过点 (1, 0) 和 (3, 0)，求 a 与 b 的值。",
    "若函数 y = (m-3)x^(m^2-7) 是二次函数，求 m 的值。",
]

# ---------- 模拟学生行为模板 ----------
GENERIC_ATTEMPTS = [
    "我先算了一下，然后就不会了……",
    "我算出来 k > 1/2，对吗？",
    "是不是要先算 Δ > 0？",
    "这一步为什么要这么变？我不太明白。",
    "哦我好像懂了，那下一步是不是代入就行？",
    "我算出 a = 2 对不对？",
]

DISTRACTED = [
    "老师我有点走神，能再讲一遍吗？",
    "刚才没听懂……这题和平时作业有什么关系吗？",
    "（发呆了一会儿）你刚说到哪了？",
]

DEMAND_ANSWER = [
    "直接告诉我答案吧，我赶时间。",
    "答案到底是多少？我抄一下。",
]

GIVE_UP = [
    "不会，太难了。",
    "算了吧，我数学本来就不行。",
]

OFF_TOPIC = [
    "我们班同学说这个知识点不考了，真的吗？",
    "老师，中考还有多久？我有点慌。",
]


def student_reply(rng: random.Random) -> str:
    """行为概率：作答 60% / 走神 15% / 要答案 10% / 放弃 10% / 跑题 5%"""
    r = rng.random()
    if r < 0.60:
        return rng.choice(GENERIC_ATTEMPTS)
    if r < 0.75:
        return rng.choice(DISTRACTED)
    if r < 0.85:
        return rng.choice(DEMAND_ANSWER)
    if r < 0.95:
        return rng.choice(GIVE_UP)
    return rng.choice(OFF_TOPIC)


# ---------- 大模型模拟学生（≤100 轮测试推荐，默认） ----------
# 画像随机组合且刻意避免刻板印象：年级/水平/性格/注意力/表达/状态/动机自由组合，
# 允许出现「基础好但极度焦虑」「沉默寡言却爱追问」等非常规组合。

PERSONA_DIMS = {
    "年级": ["初一", "初二", "初三", "高一", "高二"],
    "数学水平": [
        "基础薄弱、计算易错，但愿意努力",
        "中上水平但非常粗心",
        "概念清楚、计算快，但不会综合运用",
        "平时能及格，遇到压轴题就慌",
        "成绩不错，但靠背题型，换情境就不会",
        "基础尚可，但速度慢、每一步都要想很久",
    ],
    "性格": [
        "话多外向",
        "沉默寡言、回复极简",
        "容易焦虑",
        "佛系慢热",
        "好胜、喜欢质疑",
        "爱面子、怕被说笨",
    ],
    "注意力": [
        "专注",
        "容易走神",
        "间歇性走神、需要被拉回来",
        "容易被手机消息分心",
    ],
    "表达习惯": [
        "口语化、偶尔带表情符号",
        "喜欢把步骤写出来",
        "常反问「为什么」",
        "回复很短、通常只说答案",
    ],
    "对AI的态度": [
        "信任、认真配合",
        "半信半疑，偶尔测试AI会不会",
        "敷衍、想快点结束",
        "依赖、总想要答案",
    ],
    "当前状态": [
        "刚做完作业有点累",
        "明天要模考，很紧张",
        "刚被家长批评，心情差",
        "刚上完体育课，很兴奋",
        "晚饭前有点饿，想快点做完",
        "状态不错，愿意多想",
    ],
    "来练题的动机": [
        "自己想提分",
        "家长要求来的",
        "对压轴题本身感兴趣",
        "只求做完不被骂",
    ],
}


def random_persona(rng: random.Random) -> str:
    """随机组合一份学生画像（刻意不做固定人设，避免刻板印象）。"""
    parts = [rng.choice(pool) for pool in PERSONA_DIMS.values()]
    return "、".join(parts)


LLM_STUDENT_SYSTEM = """你正在扮演一名真实的中学生，用一款「追问式 AI 讲题教练」练习数学题。请始终遵守：
1. 严格按下面的「学生画像」说话：水平、性格、注意力、情绪、表达方式都要符合画像。
2. 回复自然、简短（一般 1~3 句话），像真实学生在打字。
3. 可以算错、走神、不耐烦、要答案、问无关问题，但不要脱离角色。
4. 不要提到「扮演」「提示词」「模型」等词，不要复述画像内容。
5. 用中文回复。"""


class LLMStudent:
    def __init__(self, persona: str):
        self.persona = persona

    def reply(self, transcript: str) -> str:
        return client.chat(
            [
                {
                    "role": "system",
                    "content": LLM_STUDENT_SYSTEM + "\n\n学生画像：" + self.persona,
                },
                {
                    "role": "user",
                    "content": "对话记录：\n" + transcript + "\n\n请以学生的身份，给出你现在的回复。",
                },
            ],
            temperature=1.0,
            max_tokens=200,
        )


def classify_behavior_llm(text: str) -> str:
    """对大模型学生的回复做粗分类（仅用于统计标签）。"""
    if any(k in text for k in ("不会", "太难", "算了", "放弃")):
        return "放弃"
    if any(k in text for k in ("答案", "告诉我", "直接给")):
        return "要答案"
    if any(k in text for k in ("走神", "没听", "再说一遍", "没懂", "发呆")):
        return "走神"
    if any(k in text for k in ("不考", "有用吗", "为什么要学")):
        return "跑题"
    return "作答"


def classify_behavior(text: str) -> str:
    for label, pool in [
        ("走神", DISTRACTED),
        ("要答案", DEMAND_ANSWER),
        ("放弃", GIVE_UP),
        ("跑题", OFF_TOPIC),
    ]:
        if text in pool:
            return label
    return "作答"


# ---------- 会话评估 ----------
EVAL_SYSTEM = (
    "你是讲题质量评估员。阅读「AI 讲题教练与学生」的完整对话，按 5 个维度打分（1-5 的整数），"
    "并给出一句话总结（指出最需要改进的一点）。评分规则：若某维度在对话中完全未出现触发场景"
    "（如学生全程未走神、无负面情绪），该维度给 5 分，并在总结中说明「该维度未触发」。"
    "只输出 JSON，不要输出其他内容："
    '{"引导性": 数字, "正确性": 数字, "应对走神与负面情绪": 数字, "步骤与追问质量": 数字, "错因诊断": 数字, "总结": "一句话"}'
)


def evaluate_transcript(transcript: str):
    return client.chat(
        [
            {"role": "system", "content": EVAL_SYSTEM},
            {"role": "user", "content": transcript},
        ],
        temperature=0.2,
    )


# ---------- 主流程 ----------
def load_questions():
    if config.QUESTION_BANK.exists():
        try:
            bank = json.loads(config.QUESTION_BANK.read_text(encoding="utf-8"))
            qs = [q["question"] for q in bank.get("questions", []) if q.get("status") == "ready"]
            if qs:
                return qs
        except json.JSONDecodeError:
            pass
    return FALLBACK_QUESTIONS


def run_session(question, province, grade, rounds, rng, simulator):
    """simulator：LLMStudent（大模型模拟）或 student_reply（脚本模板）。返回（转录, 行为标签）。"""
    s = engine.Session(province, grade)
    behaviors = []
    transcript_lines = []

    r = s.start(question)
    transcript_lines.append("教练：" + r["reply"])

    for i in range(rounds):
        if isinstance(simulator, LLMStudent):
            stu = simulator.reply("\n".join(transcript_lines))
            behaviors.append(classify_behavior_llm(stu))
        else:
            stu = simulator(rng)
            behaviors.append(classify_behavior(stu))
        transcript_lines.append("学生：" + stu)
        r = s.reply(stu)
        transcript_lines.append("教练：" + r["reply"])

    unlock = s.unlock()
    transcript_lines.append("教练（完整讲解）：" + unlock)
    summary = s.summarize()
    transcript_lines.append("教练（掌握度小结）：" + summary)

    return "\n".join(transcript_lines), behaviors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=10, help="会话数（默认 10）")
    ap.add_argument("--rounds", type=int, default=8, help="每会话追问轮数（默认 8）")
    ap.add_argument(
        "--student",
        choices=["llm", "script"],
        default="llm",
        help="学生模拟方式：llm=大模型模拟（100轮内推荐，默认），script=模板（极大量测试用）",
    )
    ap.add_argument("--seed", type=int, default=20260910)
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不调用 API")
    args = ap.parse_args()

    student_turns = args.sessions * args.rounds
    total_rounds = args.sessions * (1 + args.rounds * 2 + 2)
    print(f"计划：{args.sessions} 个会话 × 每会话 {args.rounds} 轮追问")
    print(f"学生发言（LLM 模拟）：{student_turns} 轮，全部对话回合约 {total_rounds} 轮")
    print(f"学生模拟方式：{args.student}")
    if args.dry_run:
        return

    rng = random.Random(args.seed)
    questions = load_questions()
    report = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "settings": {"sessions": args.sessions, "rounds": args.rounds, "student": args.student},
        "sessions": [],
    }

    for i in range(args.sessions):
        q = questions[i % len(questions)]
        province = "通用"
        grade = rng.choice(config.GRADES[1:]) if len(config.GRADES) > 1 else "通用"
        persona = None
        if args.student == "llm":
            persona = random_persona(rng)
            simulator = LLMStudent(persona)
        else:
            simulator = student_reply
        try:
            transcript, behaviors = run_session(q, province, grade, args.rounds, rng, simulator)
            eval_raw = evaluate_transcript(transcript)
            try:
                scores = json.loads(eval_raw)
            except json.JSONDecodeError:
                scores = {"引导性": -1, "正确性": -1, "应对走神与负面情绪": -1,
                          "步骤与追问质量": -1, "错因诊断": -1, "总结": eval_raw[:120]}
        except client.NoApiKeyError as e:
            print("ERROR:", e)
            return
        except client.BudgetExceededError as e:
            print("WARNING:", e, "—— 超支即停，本次测试到此为止。")
            break

        status = client.budget_status()
        report["sessions"].append(
            {
                "index": i + 1,
                "question": q[:60],
                "province": province,
                "grade": grade,
                "persona": persona,
                "behaviors": behaviors,
                "scores": scores,
                "transcript": transcript,
            }
        )
        print(
            f"[{i + 1}/{args.sessions}] 年级: {grade} ｜ 画像: {(persona or '脚本模板')[:56]} ｜ "
            f"行为: {behaviors} ｜ "
            f"评分: 引导性 {scores.get('引导性')} / 正确性 {scores.get('正确性')} / "
            f"走神应对 {scores.get('应对走神与负面情绪')} ｜ 累计 ¥{status['total_spent']}"
        )
        if scores.get("总结"):
            print(f"      经验总结：{scores['总结']}")

    # 汇总
    dims = ["引导性", "正确性", "应对走神与负面情绪", "步骤与追问质量", "错因诊断"]
    avg = {}
    for d in dims:
        vals = [s["scores"].get(d) for s in report["sessions"] if isinstance(s["scores"].get(d), int) and s["scores"].get(d) > 0]
        avg[d] = round(sum(vals) / len(vals), 2) if vals else None
    report["aggregate"] = {"avg_scores": avg, "total_sessions": len(report["sessions"])}

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "test_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# 模拟学生测试汇总（中下水平 / 注意力不集中）",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 会话数：{len(report['sessions'])}，总轮次约：{len(report['sessions']) * (1 + args.rounds * 2 + 2)}",
        "- 平均分：" + " ｜ ".join(f"{d}={avg[d]}" for d in dims if avg[d] is not None),
        f"- 累计花费：¥{client.budget_status()['total_spent']}",
        "",
        "## 各会话经验总结",
        "",
    ]
    for s in report["sessions"]:
        lines.append(f"### 会话 {s['index']}（{s['question']}…）")
        lines.append(f"- 学生画像：{s.get('persona')}")
        lines.append(f"- 学生行为触发：{'、'.join(s['behaviors'])}")
        sc = s["scores"]
        lines.append(
            "- 评分：" + " ｜ ".join(f"{d}={sc.get(d)}" for d in dims)
        )
        lines.append(f"- 经验总结：{sc.get('总结', '无')}")
        lines.append("")
    lines += [
        "## 整体结论与下一步建议",
        "",
        '- 若「引导性」均值 < 4：在 `tutor/prompts.py` 的 SYSTEM 中加强「不直接给答案」约束，并增加"学生索要答案时的标准回应"示例',
        '- 若「应对走神与负面情绪」均值 < 4：SYSTEM 中补充规则"学生走神时先安抚、再简短重述当前步骤"',
        "- 若「正确性」均值 < 4：回到 `quality/run_check.py` 对拍抽检，优先修题目集而非提示词",
        "- 把得分 < 3 的会话转录复制到 `quality/评分表模板.md` 记录表里，逐条修订",
    ]
    (config.DATA_DIR / "test_summaries.md").write_text("\n".join(lines), encoding="utf-8")

    print("\n报告已保存：data/test_report.json 与 data/test_summaries.md")
    print("平均分：", avg)
    print("累计花费：", client.budget_status())


if __name__ == "__main__":
    main()
