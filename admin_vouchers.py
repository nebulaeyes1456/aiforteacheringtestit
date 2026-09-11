"""兑换码管理（闲鱼结算：随机密钥兑时长，买多少用多少）。

台账：data/vouchers.json（含生成/使用/退款记录，勿删，供退款核算与审计）。

用法（在 app 目录下）：
  python admin_vouchers.py gen --hours 2 --count 5 --note "闲鱼订单号xxxx"
  python admin_vouchers.py list
  python admin_vouchers.py refund TUT-XXXX-XXXX-XXXX
"""
import argparse
import datetime as dt
import json
import secrets

from tutor import config

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去除易混淆字符（0/O/1/I）


def make_key() -> str:
    return "TUT-" + "-".join(
        "".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(3)
    )


def load():
    if config.VOUCHER_FILE.exists():
        try:
            return json.loads(config.VOUCHER_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"vouchers": {}}


def save(data):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.VOUCHER_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def remaining_seconds(v) -> float:
    return max(round(v.get("hours", 0.0) * 3600 - v.get("seconds_used", 0.0), 1), 0.0)


def cmd_gen(args):
    data = load()
    print(f"生成 {args.count} 个兑换码，每个 {args.hours} 小时"
          f"（参考价 ¥{args.hours * config.VOUCHER_PRICE_PER_HOUR:.2f}，按 {config.VOUCHER_PRICE_PER_HOUR:.0f} 元/小时）：")
    print()
    for _ in range(args.count):
        key = make_key()
        while key in data["vouchers"]:
            key = make_key()
        data["vouchers"][key] = {
            "hours": args.hours,
            "seconds_used": 0.0,
            "created": dt.datetime.now().isoformat(timespec="seconds"),
            "note": args.note or "",
            "status": "active",
        }
        print(f"  {key}")
    save(data)
    print()
    print("请将上面的兑换码私发给对应买家。台账已存入 data/vouchers.json。")


def cmd_list(args):
    data = load()
    vs = data["vouchers"]
    if not vs:
        print("暂无兑换码。")
        return
    print(f"{'兑换码':<22}{'总时长':>6}{'已用(分)':>8}{'剩余(分)':>8}  {'状态':<10}{'备注'}")
    for k, v in sorted(vs.items()):
        used_min = round(v.get("seconds_used", 0.0) / 60, 1)
        rem_min = round(remaining_seconds(v) / 60, 1)
        print(f"{k:<22}{v['hours']:>6.1f}{used_min:>8.1f}{rem_min:>8.1f}  "
              f"{v.get('status', 'active'):<10}{v.get('note', '')}")


def cmd_refund(args):
    data = load()
    v = data["vouchers"].get(args.key)
    if not v:
        print("兑换码不存在：", args.key)
        return
    if v.get("status") != "active":
        print(f"该兑换码已处于「{v.get('status')}」状态，无需重复退款。")
        return
    rem_h = round(remaining_seconds(v) / 3600, 2)
    refund = round(rem_h * config.VOUCHER_PRICE_PER_HOUR, 2)
    v["status"] = "refunded"
    v["refunded_at"] = dt.datetime.now().isoformat(timespec="seconds")
    v["refund_hours"] = rem_h
    v["refund_yuan"] = refund
    save(data)
    print(f"已标记退款：{args.key}")
    print(f"  剩余 {rem_h} 小时 × {config.VOUCHER_PRICE_PER_HOUR:.0f} 元/小时 = 应退 ¥{refund}")
    print("请在闲鱼按此金额退款并保留聊天/转账记录。台账已更新。")


def main():
    ap = argparse.ArgumentParser(description="兑换码管理")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_gen = sub.add_parser("gen")
    p_gen.add_argument("--hours", type=float, required=True, help="每个兑换码的时长（小时）")
    p_gen.add_argument("--count", type=int, default=1)
    p_gen.add_argument("--note", default="", help="备注（建议填闲鱼订单号）")
    p_gen.set_defaults(func=cmd_gen)
    p_list = sub.add_parser("list")
    p_list.set_defaults(func=cmd_list)
    p_refund = sub.add_parser("refund")
    p_refund.add_argument("key", help="兑换码")
    p_refund.set_defaults(func=cmd_refund)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
