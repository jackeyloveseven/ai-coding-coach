#!/usr/bin/env python3
"""Mastery ledger: record a mastery level per topic and work out what is due for
spaced review. Standard library only.

Usage:
  ledger.py record <topic> <pass|partial|fail> [--note "one sentence"] [--level 0-4]
  ledger.py due [--limit N]      list the topics due for review
  ledger.py show                 every topic, with tier suggestions
  ledger.py card                 print a pasteable study card (for hosts with no local filesystem)
  ledger.py path                 show where the ledger file lives

Ledger location: the COACH_LEDGER environment variable, defaulting to
~/.ai-coding-coach/ledger.json
For testing: COACH_TODAY=YYYY-MM-DD overrides "today".

Only topic tags, outcomes and a one-sentence note are stored. Never store code,
hostnames, internal addresses, keys, or colleague names.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

LEVELS = {0: "not yet", 1: "can read", 2: "can predict", 3: "can write unaided", 4: "can find bugs, can teach"}
# Review interval in days for each mastery level
INTERVAL = {0: 1, 1: 3, 2: 7, 3: 16, 4: 35}
ADVICE = {
    0: "default tier; raise one if needed",
    1: "default tier; raise one if needed",
    2: "default tier",
    3: "can drop one tier (keep the one-line silent risk)",
    4: "can drop one tier (keep the one-line silent risk)",
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
            raise ValueError("missing the topics field")
        return data
    except (json.JSONDecodeError, ValueError) as e:
        # Better to fail than to overwrite a file that might still be recoverable
        sys.exit(f"could not read the ledger: {p}\nreason: {e}\ncheck or back up that file first; this script will not overwrite it.")


def save(data: dict) -> None:
    p = ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temporary file and replace, so a half-finished write can't corrupt
    # the ledger
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
        sys.exit("topic tags may use only lowercase letters, digits, dots, underscores and hyphens, up to 60 characters - for example dpo-loss or attention-mask.")
    if args.level is not None and args.level not in LEVELS:
        sys.exit("--level must be between 0 and 4.")

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
    entry["history"] = entry["history"][-10:]  # keep only the most recent 10
    data["topics"][topic] = entry
    save(data)
    print(f"{topic}: level {old} -> {new} ({LEVELS[new]}), next review {entry['next']}")


def cmd_due(args) -> None:
    data = load()
    now = today()
    rows = []
    for topic, e in data["topics"].items():
        nxt = date.fromisoformat(e["next"])
        if nxt <= now:
            rows.append(((now - nxt).days, e["level"], topic, e))
    # Lowest level first, then the most overdue
    rows.sort(key=lambda r: (r[1], -r[0]))
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print("nothing is due for review today.")
        return
    for overdue, level, topic, e in rows:
        last = e["history"][-1] if e["history"] else {}
        note = f" | last note: {last['note']}" if last.get("note") else ""
        print(f"{topic} | level {level} ({LEVELS[level]}) | overdue {overdue}d{note}")


def cmd_show(_args) -> None:
    data = load()
    if not data["topics"]:
        print("the ledger is still empty.")
        return
    now = today()
    print("topic | level | last | next review | tier suggestion")
    for topic, e in sorted(data["topics"].items(), key=lambda kv: (kv[1]["level"], kv[0])):
        due = " (due)" if date.fromisoformat(e["next"]) <= now else ""
        print(f"{topic} | {e['level']} {LEVELS[e['level']]} | {e['last']} | {e['next']}{due} | {ADVICE[e['level']]}")


def cmd_card(_args) -> None:
    data = load()
    now = today()
    print(f"# Study card (exported {now.isoformat()})")
    print("Save this in your own notes, and paste it back at the start of the next conversation.\n")
    print("| Topic | Level | Last | Next review |")
    print("|---|---|---|---|")
    for topic, e in sorted(data["topics"].items(), key=lambda kv: (kv[1]["level"], kv[0])):
        print(f"| {topic} | {e['level']} {LEVELS[e['level']]} | {e['last']} | {e['next']} |")
    weak = []
    for topic, e in data["topics"].items():
        for h in e["history"][-3:]:
            if h["result"] != "pass" and h["note"]:
                weak.append(f"- {topic}: {h['note']}")
    if weak:
        print("\nRecurring mistakes:")
        print("\n".join(weak[:8]))


def main() -> None:
    ap = argparse.ArgumentParser(description="mastery ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record", help="record one outcome")
    r.add_argument("topic")
    r.add_argument("result", choices=["pass", "partial", "fail"])
    r.add_argument("--note", default="")
    r.add_argument("--level", type=int, default=None, help="set the level 0-4 directly when the evidence is strong")
    r.set_defaults(fn=cmd_record)

    d = sub.add_parser("due", help="list the topics due for review")
    d.add_argument("--limit", type=int, default=0)
    d.set_defaults(fn=cmd_due)

    sub.add_parser("show", help="show everything").set_defaults(fn=cmd_show)
    sub.add_parser("card", help="export a study card").set_defaults(fn=cmd_card)
    sub.add_parser("path", help="show the ledger location").set_defaults(fn=lambda _a: print(ledger_path()))

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
