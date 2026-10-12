#!/usr/bin/env python3
"""通用进度读取器：从一次运行的目录里读指标，切成若干段打印趋势。

用法：
  generic.py <运行目录> [--segments 8] [--limit 6]

按这个顺序找指标，用找到的第一种：
  1. *.jsonl                每行一个 JSON
  2. trainer_state.json     HuggingFace Trainer / TRL 的 SFT、DPO 都会写
  3. events.out.tfevents.*  tensorboard（需要远端装了 tensorboard）
  4. 日志里的 loss=0.12、reward: 0.5 这类文字

只打印每段的平均值。单步值跳动大，没有信息量，看的是从左到右的趋势。
名字里带 loss、reward、acc、margin、grad、kl、lr 的指标优先显示。

这个脚本会被 exp 用管道送到远端执行（ssh 机器 "python3 - 目录" < generic.py），
所以不要 import 本目录下的其他文件，也别依赖运行时的工作目录。
"""

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_SEGMENTS = 8
DEFAULT_LIMIT = 6
PREFER = ("loss", "reward", "acc", "margin", "grad", "kl", "lr")

# 这些名字是元数据，不是指标。只有 6 个显示位，别让它们占掉。
# 用 --all 可以关掉这个过滤。只做整名匹配，所以 step_time、num_steps 不会被误伤。
SKIP = {"step", "steps", "epoch", "epochs", "global_step", "timestamp", "wall_time", "elapsed"}

# 单个文件最多读末尾这么多字节。训练日志动辄几 GB，全读进来会把内存吃满。
MAX_BYTES = 20 * 1024 * 1024

# 日志文字里的指标：loss=0.12、reward: 0.5、grad_norm = 1.2e-3、change=+0.3
TEXT_METRIC = re.compile(
    r"([A-Za-z_][A-Za-z0-9_./-]*)\s*[:=]\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
)


def is_number(value):
    """bool 是 int 的子类，但 true/false 不是指标。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def iter_lines(path):
    """逐行读文本文件；文件太大就只读末尾那一段。"""
    size = path.stat().st_size
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        if size > MAX_BYTES:
            handle.seek(size - MAX_BYTES)
            handle.readline()  # 丢掉可能被截断的半行
        for line in handle:
            yield line


def add_row(series, row):
    if not isinstance(row, dict):
        return
    for key, value in row.items():
        if is_number(value):
            series.setdefault(key, []).append(float(value))


def from_jsonl(path):
    series = {}
    for line in iter_lines(path):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        add_row(series, row)
    return series


def from_trainer_state(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return {}
    series = {}
    for row in data.get("log_history") or []:
        add_row(series, row)
    return series


def from_tfevents(paths):
    """读 tensorboard 事件文件。没装 tensorboard 就返回 None（表示「没法试」，不是「没有指标」）。"""
    try:
        from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    except ImportError:
        return None
    series = {}
    for path in paths:
        accumulator = EventAccumulator(str(path))
        accumulator.Reload()
        for tag in accumulator.Tags().get("scalars", []):
            series[tag] = [event.value for event in accumulator.Scalars(tag)]
    return series


def from_log_text(paths):
    series = {}
    for path in paths:
        for line in iter_lines(path):
            for name, value in TEXT_METRIC.findall(line):
                try:
                    series.setdefault(name, []).append(float(value))
                except ValueError:
                    continue
    return series


def collect(run_dir):
    """返回 (series, 来源说明)；一个都找不到就返回 ({}, None)。"""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        sys.exit(f"不是目录：{run_dir}")

    for path in sorted(run_dir.glob("*.jsonl")):
        series = from_jsonl(path)
        if series:
            return series, path.name

    state = run_dir / "trainer_state.json"
    if state.is_file():
        series = from_trainer_state(state)
        if series:
            return series, state.name

    events = sorted(run_dir.glob("events.out.tfevents.*"))
    if events:
        series = from_tfevents(events)
        if series:
            return series, f"{len(events)} 个 tfevents 文件"
        if series is None:
            print("提示：找到 tfevents，但远端没装 tensorboard，跳过。", file=sys.stderr)

    logs = sorted(path for path in run_dir.rglob("*.log") if path.is_file())
    if logs:
        series = from_log_text(logs)
        if series:
            return series, f"{len(logs)} 个日志文件"

    return {}, None


def rank(name):
    """名字里带 loss/reward/acc/... 的排前面。"""
    low = name.lower()
    return (0 if any(word in low for word in PREFER) else 1, name)


def select_metrics(series, limit=DEFAULT_LIMIT, show_all=False):
    """挑出要显示的指标名：默认滤掉 step/epoch 这类元数据，按 rank 排序，最多 limit 个。

    单独抽出来给 exp report 复用——报告要跟 status 显示同一批指标。
    """
    names = list(series)
    if not show_all:
        kept = [name for name in names if name.lower() not in SKIP]
        names = kept or names  # 全被过滤掉就不过滤，宁可多显示也别什么都不显示
    return sorted(names, key=rank)[:limit]


def segments(values, count):
    """把一段序列切成 count 段，返回每段的平均值。段数比点数还多时空段记 nan。"""
    total = len(values)
    out = []
    for index in range(count):
        chunk = values[index * total // count : (index + 1) * total // count]
        out.append(sum(chunk) / len(chunk) if chunk else float("nan"))
    return out


def fmt(value):
    if value != value:  # nan
        return "nan"
    if value and (abs(value) < 1e-3 or abs(value) >= 1e5):
        return f"{value:.2e}"
    return f"{value:.3g}"


def render(series, source, count, limit, show_all=False):
    names = select_metrics(series, limit, show_all)
    points = max(len(values) for values in series.values())
    count = max(1, min(count, points))

    width = max([len(name) for name in names] + [8])
    # 中文按两格宽算，所以表头补的空格要减掉「指标」占的两格
    header = "指标" + " " * max(1, width - 4)
    header += " " + " ".join(f"{index + 1:>9}" for index in range(count))
    header += f" {'变化':>8}"

    print(f"来源: {source} ｜ 共 {points} 个点 ｜ 切 {count} 段")
    print(header)
    for name in names:
        segs = segments(series[name], count)
        cells = " ".join(f"{fmt(value):>9}" for value in segs)
        print(f"{name:<{width}} {cells} {fmt(segs[-1] - segs[0]):>10}")


def dump_json(run_dir):
    """把原始序列按 JSON 输出（给 exp report 画图用）。找不到指标就是空的 series。

    和表格输出共用 collect()，所以「找哪个来源、怎么解析」只有一份实现。
    """
    series, source = collect(run_dir)
    return json.dumps({"source": source, "series": series}, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="通用进度读取器")
    parser.add_argument("run_dir", help="某一次运行的目录")
    parser.add_argument("--segments", type=int, default=DEFAULT_SEGMENTS, help="切成几段（默认 8）")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="最多显示几个指标（默认 6）")
    parser.add_argument("--all", action="store_true", help="连 step/epoch 这类元数据也一起显示")
    parser.add_argument("--json", action="store_true", help="输出原始序列的 JSON（给 exp report 用）")
    args = parser.parse_args()

    if args.json:
        # 报告要画曲线，得拿逐步的原始值，而不是分段均值。没有指标也照常输出空壳。
        print(dump_json(args.run_dir))
        return 0

    series, source = collect(args.run_dir)
    if not series:
        print(f"在 {args.run_dir} 里没找到可读的指标。")
        print("找过：*.jsonl、trainer_state.json、events.out.tfevents.*、*.log")
        print("如果这个方法的指标格式比较特殊，给它写一个专用的 progress/<方法>.py。")
        return 1

    render(series, source, args.segments, args.limit, args.all)
    return 0


if __name__ == "__main__":
    sys.exit(main())
