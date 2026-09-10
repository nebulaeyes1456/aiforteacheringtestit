# 追问式讲题教练（B 方案 MVP）

对应《B方案可执行项目书 v16.0》。当前推进阶段：W1-2（骨架 + 题库采集）→ W3-5（提示词 + 抽检流水线）。

## 目录结构

```
app/
  server.py            Flask 服务入口（本地运行）
  tutor/
    config.py          全局配置：模型、价格、预算守卫
    client.py          DeepSeek 客户端 + 记账 + 超支即停
    prompts.py         讲题提示词（追问式 / 完整讲解 / 抽检）
    engine.py          会话状态机（引导 3 轮后可解锁）
  templates/index.html 前端页面（无构建，纯 HTML/JS）
  quality/
    run_check.py       对拍抽检流水线（模型答案 vs 官方答案）
    评分表模板.md       5 维度人工评分表
  data/
    question_bank.json 题库（开发样例 + 真题录入格式）
  scripts/fetch_papers.md  真题采集指南
```

## 快速开始

1. 配置 API Key：直接用记事本打开 `app/.env`，把密钥粘贴到 `DEEPSEEK_API_KEY=` 后面保存即可（该文件已被 .gitignore 忽略，不会外传）
2. 安装依赖：`pip install -r requirements.txt`
3. 启动：`python server.py` → 打开 http://127.0.0.1:8000
4. 粘贴题目开始引导；追问 3 轮后或随时可「解锁完整讲解」
5. 顶部可选省份；点「🎲 随机练一题」从题库抽题（不同省份随机混排）

## 预算守卫（项目书 §5 控费机制）

- 总预算 180 元 + 日限额 3 元，可用环境变量调整：`TUTOR_API_BUDGET` / `TUTOR_DAILY_CAP`
- 内测成本控制：每人上限 `TUTOR_BETA_CAP`（默认 0.25 元）、人数上限 `TUTOR_BETA_USERS`（默认 1000）、内测周期 `TUTOR_BETA_DAYS`（默认 14 天，从第一个用户起算，到期自动停止服务），按匿名客户端 ID 记账（`data/user_usage.json`）
- 每次调用自动记账到 `data/usage.json`；**超支即停**
- 查看：页面顶部预算条，或 `GET /api/status`

## 质量抽检（项目书 §6）

```
python -m quality.run_check --n 3 --limit 10
```

- 每道题让模型独立解 n 次，与 `official_answer` 对拍（一致/不一致/无法判断）
- 报告输出 `data/check_report.json`；上线门槛：正确率 ≥95%
- 人工评分表见 `quality/评分表模板.md`

## 待办（W1-2）

- [ ] 软件内已支持省份选择（默认「通用」），无需改代码
- [ ] 采集 50 道官方真题 + 官方公开模拟题（多省份）→ `data/question_bank.json`（指南见 `scripts/fetch_papers.md`）
- [ ] 抽检正确率 ≥95% 后才对真实学生开放

## 效果测试（模拟学生）

```
# ≤100 轮用大模型模拟学生（默认，画像随机组合、避免刻板印象）
python test_student.py --sessions 10 --rounds 8

# 极大量测试用脚本模板（学生端不调 API，更省钱）
python test_student.py --sessions 50 --rounds 5 --student script
```

每会话自动评估（5 维度）并生成经验总结，结果见 `data/test_report.json` 与 `data/test_summaries.md`。

## 让用户用上（部署与「安装」）

- 已内置 PWA：用户用 Chrome/Edge 打开网址点「⬇️ 安装到桌面」，或手机浏览器菜单「添加到主屏幕」，即可像 App 一样使用，无需应用商店
- 公网部署两条路：
  1. 应急演示：cpolar 等内网穿透（当天可用、免费，但域名随机、不稳定，仅适合小范围演示）
  2. 正式内测：轻量云服务器（约 10~30 元/月）+ 域名 + ICP 备案（需经营主体，周期 2~4 周，须提前办理）
- 服务器部署要点：安装依赖、设置 `DEEPSEEK_API_KEY` 环境变量、`waitress-serve --host 0.0.0.0 --port 8000 server:app`、配置 HTTPS
- 提醒：ICP 备案是硬性前置，建议尽早启动

## 合规提醒（项目书 §8）

游客模式、无账号、不收集任何身份信息；题目即用即清；只使用省级考试院官方公开真题。
