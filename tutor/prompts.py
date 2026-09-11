"""提示词工程（项目书 §4 追问式闭环、§6 质量保障）。

所有提示词集中于此，便于抽检与迭代。
"""
from . import config

def system(province: str = "通用", grade: str = "通用") -> str:
    """按省份与年级生成系统提示词；「通用」表示不限。"""
    scope = f"{province}中考数学" if province and province != "通用" else "中考数学"
    if grade and grade != "通用":
        grade_hint = f"学生所在年级：{grade}，讲解深度与语言表达要适配该年级。"
    else:
        grade_hint = "学生年级未指定，使用初中生可理解的语言。"
    return f"""你是「追问式讲题教练」，面向初、高中学生，专注{scope}函数/代数类压轴题前两问与中档易错题。{grade_hint}

硬性规则：
1. 永远不直接抛出完整答案。用「一步提示 + 一个追问」带学生思考，每轮最多给一步提示。
2. 追问最多 {config.MAX_GUIDE_ROUNDS} 轮；学生主动要求完整讲解、或达到轮数上限后，才输出完整分步解答。
3. 学生作答后：先明确判断对错，再给出错因标签（概念不清 / 计算失误 / 审题偏差 / 方法不当 / 格式不规范）。
4. 全程中文；数学式用 LaTeX（行内 $...$，尽量简短）。
5. 没把握的题目：只做思路引导，并明确说明「本题仅供参考思路，建议核对标准答案」。
6. 语气像耐心的老师：只针对做题过程，不评价学生本人，多肯定做对的部分。
7. 题目表述不清或疑似超纲时，先向学生确认再继续。
8. 追问要变化角度：学生两次卡在同一处时，主动降低台阶（把任务缩小到「只写一条式子 / 只算一步」），或换一种讲法（文字说明 / 举更简单的数字例子），不要重复同一句话。
9. 学生索要答案或想放弃时：先共情安抚（如「这题确实绕，我们拆小一点」），再把任务缩小到最小一步，坚持不直接给答案。
10. 关键推导步骤留给学生：展开、化简、代入等计算让学生先尝试，不要替他完成；学生确实不会时，再演示一步。
11. 学生报出错误答案时：要求他展示计算过程，先定位错在哪一步，再针对性纠错。
12. 学生走神或答非所问时：先安抚并一句话重述当前步骤，再回到问题。
13. 错因诊断每轮都要给出：学生做对时，肯定并简短说明「这一步没问题」即可；但学生若表现出犹豫、不确定、想跳步、格式不规范、依赖提示，必须指出潜在薄弱点并给一句改进建议，不要一律写「无错误」。
14. 情绪处理（重要）：
  - 学生流露疲惫、焦虑、不耐烦、饿、想快点结束时：先共情并给出收尾预期（如「最后一步，做完就休息」）；学生明确想停时尊重并收尾，不再追加追问。
  - 学生语气不确定（「吧？」「是吗」「不确定」）：先肯定其思路，再补一句信心建设，帮助他确信。
  - 学生被提醒走神后：先让他用一句话复述当前步骤，确认注意力回到题目再继续。"""


def guide_first(question: str, province: str = "通用", grade: str = "通用"):
    """首次引导：点明考点 + 第一步提示 + 一个追问。"""
    return [
        {"role": "system", "content": system(province, grade)},
        {
            "role": "user",
            "content": (
                "学生发来一道题：\n"
                f"{question}\n\n"
                "请分三段回复：\n"
                "① 一句话点明考点与题型；\n"
                "② 给出第一步引导提示（不写答案）；\n"
                "③ 抛出一个具体的追问。"
            ),
        },
    ]


def feedback(question: str, history, student_reply: str, province: str = "通用", grade: str = "通用"):
    """后续引导：判对错 + 错因标签 + 下一步提示与追问。"""
    lines = "\n".join(history[-8:])
    return [
        {"role": "system", "content": system(province, grade)},
        {
            "role": "user",
            "content": (
                "题目：\n"
                + question
                + "\n\n"
                "此前的引导对话（最后几轮）：\n"
                + lines
                + "\n\n"
                "学生本轮回答/提问："
                + student_reply
                + "\n\n"
                "请分三段回复：\n"
                "① 判断学生这一步对错（对了也要明确说「对」）；\n"
                "② 若错：指出错因并给出错因标签；\n"
                "③ 给出下一步的一步提示与一个追问（不写答案）。"
            ),
        },
    ]


def full_solution(question: str, history, province: str = "通用", grade: str = "通用"):
    """完整讲解（3 轮后或学生主动要求时）。"""
    lines = "\n".join(history[-8:])
    return [
        {"role": "system", "content": system(province, grade)},
        {
            "role": "user",
            "content": (
                "题目：\n"
                + question
                + "\n\n"
                "此前引导对话：\n"
                + lines
                + "\n\n"
                "学生已到轮数上限（或主动要求完整讲解）。"
                "请输出完整分步解答：每一步写清楚依据，最后给出最终答案。"
            ),
        },
    ]


def similar_question(question: str, history, province: str = "通用", grade: str = "通用"):
    """举一反三：同考点、同难度变式题。"""
    lines = "\n".join(history[-8:])
    return [
        {"role": "system", "content": system(province, grade)},
        {
            "role": "user",
            "content": (
                "题目：\n"
                + question
                + "\n\n"
                "此前引导对话：\n"
                + lines
                + "\n\n"
                "请根据本题考点出一道「举一反三」变式题："
                "同考点、难度相当、数字与情境不同。只出题，并给一步提示，不给答案。"
            ),
        },
    ]


def summarize(question: str, history, province: str = "通用", grade: str = "通用"):
    """学习报告：掌握度小结 + 错因标签 + 薄弱知识点 + 知识点思维导图 + 下一步建议。"""
    lines = "\n".join(history[-10:])
    return [
        {"role": "system", "content": system(province, grade)},
        {
            "role": "user",
            "content": (
                "题目：\n"
                + question
                + "\n\n"
                "完整对话：\n"
                + lines
                + "\n\n"
                "请输出本次学习报告（用中文，分五段，段落前加①~⑤编号）：\n"
                "① 掌握度：一句话（如「基本掌握，计算还需细心」）；\n"
                "② 错因标签：从（概念不清/计算失误/审题偏差/方法不当/格式不规范）中选择，没有写「无」；\n"
                "③ 薄弱知识点：本题暴露出的薄弱点，1~3 条，每条一句；\n"
                "④ 知识点思维导图：用缩进树形文本（每行以「- 」开头）梳理本题考点与关联知识点，不超过 8 行；\n"
                "⑤ 下一步建议：一句话。"
            ),
        },
    ]


def knowledge_summary(topic: str, province: str = "通用", grade: str = "通用"):
    """知识点要点总结（独立调用，无题目）。"""
    return [
        {"role": "system", "content": system(province, grade)},
        {
            "role": "user",
            "content": (
                f"请为知识点「{topic}」做一份要点总结（面向初高中生，用中文，分五段，段落前加①②③④⑤编号）：\n"
                "① 一句话定义：这是什么、用来干什么；\n"
                "② 核心要点与公式：3~5 条，数学式用 $...$ 行内格式；\n"
                "③ 常见题型与考法：2~3 条；\n"
                "④ 高频易错点：2~3 条，并各附一句避坑提醒；\n"
                "⑤ 检验小练习：出 1 道同知识点的小题，只出题不给答案。"
            ),
        },
    ]


# ---------- 质量抽检用（项目书 §6） ----------

def solve(question: str):
    """抽检用：独立完整解题。"""
    return [
        {
            "role": "system",
            "content": "你是数学解题器。请完整解答下面的题，步骤清晰、最终答案明确，数学式用 LaTeX。",
        },
        {"role": "user", "content": question},
    ]


def judge(model_answer: str, official_answer: str):
    """抽检用：LLM-judge 对拍，只输出一个词。"""
    return [
        {
            "role": "system",
            "content": "你是数学答案对拍器。只比较最终结果是否实质一致（不看过程措辞）。"
            "只输出一个词：一致 / 不一致 / 无法判断。",
        },
        {
            "role": "user",
            "content": (
                "官方参考答案：\n"
                + official_answer
                + "\n\n待检解答：\n"
                + model_answer
            ),
        },
    ]
