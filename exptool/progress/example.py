#!/usr/bin/env python3
"""Template for a method-specific progress reader. Copy it to
progress/<your method>.py and replace the file-reading part with your format.

How exp finds a reader: a method column of `awm-hps` looks for `progress/awm.py`
(the part before the `-`). With no match it falls back to `progress/generic.py`.
So sft, dpo and diffusionnft work with no code at all.

When you need a dedicated reader: when the method's payoff can't be read off the
training loss. RL-style methods are the usual case - the training reward changes
prompts every step and swings wildly, so staring at it tells you nothing. What
actually shows progress is the score on a **fixed eval set**, and this template
reads that.

Convention (replace it with your own format; this is just an example):
  read <run dir>/eval.jsonl, one evaluation per line
  {"step": 200, "change": 0.12, "improved": 70, "total": 128}
    step      which step this evaluation was run at
    change    mean change relative to the starting point
    improved  number of examples that got better
    total     number of examples in the eval set

Output: one line each for the start, the latest and the best, plus the trend.

Run it the same way as the other readers:
  python3 progress/example.py <run dir>
"""

import json
import sys
from pathlib import Path

EVAL_FILE = "eval.jsonl"


def load(run_dir):
    path = Path(run_dir) / EVAL_FILE
    if not path.is_file():
        print(f"{path} not found")
        print(f"this reader reads {EVAL_FILE}, one evaluation per line:")
        print('  {"step": 200, "change": 0.12, "improved": 70, "total": 128}')
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and "change" in row:
            rows.append(row)
    return rows


def main():
    if len(sys.argv) != 2:
        print("usage: example.py <run dir>")
        return 1

    rows = load(sys.argv[1])
    if not rows:
        return 1

    first, last = rows[0], rows[-1]
    best = max(rows, key=lambda row: row["change"])

    def line(label, row):
        text = f"  {label}: step {row.get('step', '?')}  change {row['change']:+.3f}"
        if "improved" in row and "total" in row:
            text += f"  improved {row['improved']}/{row['total']}"
        return text

    print(f"fixed eval set | {len(rows)} evaluations")
    print(line("start", first))
    print(line("latest", last))
    print(line("best", best))

    delta = last["change"] - first["change"]
    print(f"  latest vs start: {delta:+.3f}")
    if delta <= 0:
        print("  -> no gain. Confirm the evaluation setup hasn't changed before suspecting the method.")


if __name__ == "__main__":
    sys.exit(main())
