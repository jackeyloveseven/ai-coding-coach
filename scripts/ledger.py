#!/usr/bin/env python3
"""掌握度台账：记录每个主题的掌握等级，并按间隔复习计算哪些到期。仅用标准库。

用法：
  ledger.py record <主题> <pass|partial|fail> [--note 一句话] [--level 0-4]
  ledger.py due [--limit N]      列出到期该复习的主题
  ledger.py show                 查看全部主题与调档建议
  ledger.py card                 输出可粘贴的「学习卡」（没有本地文件系统时用）
  ledger.py path                 显示台账文件位置

台账位置：环境变量 COACH_LEDGER，默认 ~/.ai-coding-coach/ledger.json
测试用：环境变量 COACH_TODAY=YYYY-MM-DD 可以指定「今天」。

只存主题标签、结果和一句备注。不要存代码、主机名、内网地址、密钥、同事姓名。
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

LEVELS = {0: "还没掌握", 1: "能读懂", 2: "能预测", 3: "能独立写", 4: "能找 bug、能教别人"}
# 掌握等级对应的复习间隔（天）
INTERVAL = {0: 1, 1: 3, 2: 7, 3: 16, 4: 35}
ADVICE = {
    0: "按默认档，必要时上调一档",
    1: "按默认档，必要时上调一档",
    2: "按默认档",
    3: "可降一档（保留一句静默风险）",
    4: "可降一档（保留一句静默风险）",
}
TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,59}$")


def today() -> date:
    raw = os.environ.get("COACH_TODAY")
    return date.fromisoformat(raw) if raw else date.today()


def ledger_path() -> Path:
    raw = os.environ.get("COACH_LEDGER")
    return Path(raw).expanduser() if raw else Path.home() / ".ai-coding-coach" / "ledger.json"


def load() -> dict:
    p = ledger_path()
    if not p.exists():
        return {"version": 1, "topics": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data.get("topics"), dict):
            raise ValueError("缺少 topics 字段")
        return data
    except (json.JSONDecodeError, ValueError) as e:
        # 宁可报错，也不要覆盖一份可能还有救的文件
        sys.exit(f"台账文件读取失败：{p}\n原因：{e}\n请先检查或备份该文件，脚本不会覆盖它。")


def save(data: dict) -> None:
    p = ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    # 先写临时文件再替换，避免写到一半损坏台账
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def cmd_record(args) -> None:
    topic = args.topic.strip().lower()
    if not TOPIC_RE.match(topic):
        sys.exit("主题标签只能用小写字母、数字、点、下划线、连字符，且不超过 60 字符，例如 dpo-loss、attention-mask。")
    if args.level is not None and args.level not in LEVELS:
        sys.exit("--level 必须是 0 到 4。")

    data = load()
    now = today()
    entry = data["topics"].get(topic, {"level": 0, "history": []})
    old = entry["level"]

    if args.level is not None:
        new = args.level
    elif args.result == "pass":
        new = min(4, old + 1)
    elif args.result == "fail":
        new = max(0, old - 1)
    else:
        new = old

    days = INTERVAL[new]
    if args.result == "partial":
        days = max(1, days // 2)
    elif args.result == "fail":
        days = 1

    note = (args.note or "").strip()[:80]
    entry.update({"level": new, "last": now.isoformat(), "next": (now + timedelta(days=days)).isoformat()})
    entry["history"].append({"date": now.isoformat(), "result": args.result, "note": note})
    entry["history"] = entry["history"][-10:]  # 只保留最近 10 条
    data["topics"][topic] = entry
    save(data)
    print(f"{topic}: 等级 {old} → {new}（{LEVELS[new]}），下次复习 {entry['next']}")


def cmd_due(args) -> None:
    data = load()
    now = today()
    rows = []
    for topic, e in data["topics"].items():
        nxt = date.fromisoformat(e["next"])
        if nxt <= now:
            rows.append(((now - nxt).days, e["level"], topic, e))
    # 等级低的优先，其次是逾期更久的
    rows.sort(key=lambda r: (r[1], -r[0]))
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print("今天没有到期的复习项。")
        return
    for overdue, level, topic, e in rows:
        last = e["history"][-1] if e["history"] else {}
        note = f"｜上次备注：{last['note']}" if last.get("note") else ""
        print(f"{topic}｜等级 {level}（{LEVELS[level]}）｜逾期 {overdue} 天{note}")


def cmd_show(_args) -> None:
    data = load()
    if not data["topics"]:
        print("台账还是空的。")
        return
    now = today()
    print("主题 | 等级 | 上次 | 下次复习 | 调档建议")
    for topic, e in sorted(data["topics"].items(), key=lambda kv: (kv[1]["level"], kv[0])):
        due = "（已到期）" if date.fromisoformat(e["next"]) <= now else ""
        print(f"{topic} | {e['level']} {LEVELS[e['level']]} | {e['last']} | {e['next']}{due} | {ADVICE[e['level']]}")


def cmd_card(_args) -> None:
    data = load()
    now = today()
    print(f"# 学习卡（导出于 {now.isoformat()}）")
    print("把这段存进你的笔记，下次对话开头贴给 Claude。\n")
    print("| 主题 | 等级 | 上次 | 下次复习 |")
    print("|---|---|---|---|")
    for topic, e in sorted(data["topics"].items(), key=lambda kv: (kv[1]["level"], kv[0])):
        print(f"| {topic} | {e['level']} {LEVELS[e['level']]} | {e['last']} | {e['next']} |")
    weak = []
    for topic, e in data["topics"].items():
        for h in e["history"][-3:]:
            if h["result"] != "pass" and h["note"]:
                weak.append(f"- {topic}：{h['note']}")
    if weak:
        print("\n常犯错误：")
        print("\n".join(weak[:8]))


def main() -> None:
    ap = argparse.ArgumentParser(description="掌握度台账")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record", help="记录一次结果")
    r.add_argument("topic")
    r.add_argument("result", choices=["pass", "partial", "fail"])
    r.add_argument("--note", default="")
    r.add_argument("--level", type=int, default=None, help="证据很强时直接指定等级 0-4")
    r.set_defaults(fn=cmd_record)

    d = sub.add_parser("due", help="列出到期的复习项")
    d.add_argument("--limit", type=int, default=0)
    d.set_defaults(fn=cmd_due)

    sub.add_parser("show", help="查看全部").set_defaults(fn=cmd_show)
    sub.add_parser("card", help="导出学习卡").set_defaults(fn=cmd_card)
    sub.add_parser("path", help="显示台账位置").set_defaults(fn=lambda _a: print(ledger_path()))

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
