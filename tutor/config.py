"""全局配置：模型、价格、预算守卫、项目参数。

对应《B方案可执行项目书》§5：大模型 API 预算 180 元 + 应急储备 50 元。
应急储备不自动启用：需要时把 TUTOR_API_BUDGET 调高即可。
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # app/

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")  # 无论从哪个目录启动，都能读到 app/.env
except ImportError:
    pass
DATA_DIR = BASE_DIR / "data"
USAGE_FILE = DATA_DIR / "usage.json"
STATS_FILE = DATA_DIR / "stats.json"
QUESTION_BANK = DATA_DIR / "question_bank.json"

# ---------- 模型 ----------
API_KEY_ENV = "DEEPSEEK_API_KEY"
API_BASE_URL = os.environ.get("TUTOR_API_BASE", "https://api.deepseek.com")
MODEL = os.environ.get("TUTOR_MODEL", "deepseek-chat")

# ---------- 价格（元 / 百万 token），随实际账单调整 ----------
PRICE_INPUT = float(os.environ.get("TUTOR_PRICE_INPUT", "1.0"))
PRICE_OUTPUT = float(os.environ.get("TUTOR_PRICE_OUTPUT", "2.0"))

# ---------- 预算守卫 ----------
API_BUDGET_YUAN = float(os.environ.get("TUTOR_API_BUDGET", "180"))  # 项目书：API 预算
DAILY_CAP_YUAN = float(os.environ.get("TUTOR_DAILY_CAP", "3"))      # 日限额，防跑飞

# ---------- 内测成本控制（老板口径：每人 0.25 元，上限 1000 人，周期 14 天） ----------
BETA_USER_CAP_YUAN = float(os.environ.get("TUTOR_BETA_CAP", "0.25"))  # 每人内测成本上限（元）
BETA_MAX_USERS = int(os.environ.get("TUTOR_BETA_USERS", "1000"))      # 内测人数上限
BETA_DURATION_DAYS = int(os.environ.get("TUTOR_BETA_DAYS", "14"))     # 内测周期（天），从第一个用户起算
USER_USAGE_FILE = DATA_DIR / "user_usage.json"

# ---------- 付费兑换码（闲鱼结算：随机密钥兑时长，买多少用多少） ----------
ACCESS_MODE = os.environ.get("TUTOR_MODE", "beta")  # beta=内测免费模式；private=仅兑换码可进入
VOUCHER_FILE = DATA_DIR / "vouchers.json"            # 兑换码台账（含退款记录，勿删）
VOUCHER_IDLE_CAP_SEC = int(os.environ.get("TUTOR_IDLE_CAP", "300"))  # 挂机不计费上限（秒）
VOUCHER_PRICE_PER_HOUR = float(os.environ.get("TUTOR_PRICE", "2"))   # 参考价：2 元/小时（仅用于退款核算提示）

# ---------- 讲题参数 ----------
PROVINCE = os.environ.get("TUTOR_PROVINCE", "通用")  # 默认省份，软件内可切换
PROVINCES = [
    "通用", "北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林",
    "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北",
    "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海",
    "内蒙古", "广西", "西藏", "宁夏", "新疆",
]
GRADE = os.environ.get("TUTOR_GRADE", "通用")  # 默认年级，软件内可切换
GRADES = ["通用", "初一", "初二", "初三", "高一", "高二", "高三"]
MAX_GUIDE_ROUNDS = 3                                  # 追问轮数上限（项目书 §4 兜底设计）

# ---------- 模型参数 ----------
MAX_TOKENS = 800
TEMPERATURE = 0.7
