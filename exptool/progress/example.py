#!/usr/bin/env python3
"""专用进度读取器的模板。复制成 progress/<你的方法>.py，把读文件那段改成你的格式。

exp 找读取器的规则：方法列写 `awm-hps`，就找 `progress/awm.py`（只看 `-` 前面那段）。
找不到就用 `progress/generic.py`。所以 sft、dpo、diffusionnft 不写任何代码也能直接看。

什么时候需要专用读取器：当这个方法的收益不能靠训练 loss 看出来的时候。
典型是 RL 那类——训练奖励每步换题，跳动很大，盯着看没有信息量。
真正说明问题的是**固定评测集**上的分数。这个模板就是读那个的。

约定（改成你自己的格式就行，这里只是给个例子）：
  读 <运行目录>/eval.jsonl，每行一次评测
  {"step": 200, "change": 0.12, "improved": 70, "total": 128}
    step      第几步做的这次评测
    change    相对起点的平均变化
    improved  变好的样本数
    total     评测集总样本数

输出：把起点、最新、最好各报一行，并给出趋势。

跑法和其他读取器一样：
  python3 progress/example.py <运行目录>
"""

import json
import sys
from pathlib import Path

EVAL_FILE = "eval.jsonl"


def load(run_dir):
    path = Path(run_dir) / EVAL_FILE
    if not path.is_file():
        print(f"没找到 {path}")
        print(f"这个读取器读的是 {EVAL_FILE}，一行一次评测：")
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
        print("用法: example.py <运行目录>")
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

    print(f"固定评测集 ｜ 共 {len(rows)} 次评测")
    print(line("起点", first))
    print(line("最新", last))
    print(line("最好", best))

    delta = last["change"] - first["change"]
    print(f"  最新比起点: {delta:+.3f}")
    if delta <= 0:
        print("  -> 没有涨。先确认评测口径没变，再怀疑方法本身。")


if __name__ == "__main__":
    sys.exit(main())
