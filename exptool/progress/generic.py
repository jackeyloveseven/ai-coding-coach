#!/usr/bin/env python3
"""Generic progress reader: read metrics out of one run's directory and print the
trend as a set of segment means.

Usage:
  generic.py <run dir> [--segments 8] [--limit 6]

It looks for metrics in this order and uses the first source it finds:
  1. *.jsonl                 one JSON object per line
  2. trainer_state.json      written by HuggingFace Trainer / TRL SFT and DPO
  3. events.out.tfevents.*   tensorboard (needs tensorboard installed remotely)
  4. text in the log, such as loss=0.12 or reward: 0.5

Only segment means are printed. Single-step values jump around and carry no
information; what you're reading is the direction, left to right.
Metrics whose names contain loss, reward, acc, margin, grad, kl or lr sort first.

exp pipes this script to the remote host
(ssh machine "python3 - dir" < generic.py), so don't import anything else from
this directory, and don't rely on the working directory at runtime.
"""

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_SEGMENTS = 8
DEFAULT_LIMIT = 6
PREFER = ("loss", "reward", "acc", "margin", "grad", "kl", "lr")

# These names are metadata, not metrics. There are only 6 display slots; don't
# let them take one. --all turns the filter off. Matching is on the whole name,
# so step_time and num_steps are not caught by accident.
SKIP = {"step", "steps", "epoch", "epochs", "global_step", "timestamp", "wall_time", "elapsed"}

# Read at most this many bytes from the end of a single file. Training logs run
# to several GB; reading one whole would exhaust memory.
MAX_BYTES = 20 * 1024 * 1024

# Metrics in log text: loss=0.12, reward: 0.5, grad_norm = 1.2e-3, change=+0.3
TEXT_METRIC = re.compile(
    r"([A-Za-z_][A-Za-z0-9_./-]*)\s*[:=]\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
)


def is_number(value):
    """bool is a subclass of int, but true/false aren't metrics."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def iter_lines(path):
    """Read a text file line by line; for a large file, only the tail."""
    size = path.stat().st_size
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        if size > MAX_BYTES:
            handle.seek(size - MAX_BYTES)
            handle.readline()  # drop the half line the seek probably cut
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
    """Read tensorboard event files. Returns None when tensorboard isn't installed
    (meaning "couldn't try", not "there are no metrics")."""
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
    """Returns (series, source description); ({}, None) when nothing is found."""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        sys.exit(f"not a directory: {run_dir}")

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
            return series, f"{len(events)} tfevents files"
        if series is None:
            print("note: found tfevents, but tensorboard isn't installed on the remote side; skipping.", file=sys.stderr)

    logs = sorted(path for path in run_dir.rglob("*.log") if path.is_file())
    if logs:
        series = from_log_text(logs)
        if series:
            return series, f"{len(logs)} log file(s)"

    return {}, None


def rank(name):
    """Names containing loss/reward/acc/... sort first."""
    low = name.lower()
    return (0 if any(word in low for word in PREFER) else 1, name)


def select_metrics(series, limit=DEFAULT_LIMIT, show_all=False):
    """Pick the metric names to show: by default drop step/epoch-style metadata,
    sort by rank, keep at most limit.

    Pulled out on its own so exp report can reuse it — the report has to show the
    same set of metrics as status does.
    """
    names = list(series)
    if not show_all:
        kept = [name for name in names if name.lower() not in SKIP]
        names = kept or names  # if everything was filtered, don't filter at all
    return sorted(names, key=rank)[:limit]


def segments(values, count):
    """Cut a series into count segments and return each segment's mean. Segments
    beyond the number of points come back as nan."""
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
    header = "metric" + " " * max(1, width - 6)
    header += " " + " ".join(f"{index + 1:>9}" for index in range(count))
    header += f" {'change':>10}"

    print(f"source: {source} | {points} points | {count} segments")
    print(header)
    for name in names:
        segs = segments(series[name], count)
        cells = " ".join(f"{fmt(value):>9}" for value in segs)
        print(f"{name:<{width}} {cells} {fmt(segs[-1] - segs[0]):>10}")


def dump_json(run_dir):
    """Dump the raw series as JSON (for exp report to plot). An empty series when
    no metrics are found.

    Shares collect() with the table output, so "which source, parsed how" has only
    one implementation.
    """
    series, source = collect(run_dir)
    return json.dumps({"source": source, "series": series}, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Generic progress reader")
    parser.add_argument("run_dir", help="the directory of one run")
    parser.add_argument("--segments", type=int, default=DEFAULT_SEGMENTS, help="how many segments (default 8)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="how many metrics to show at most (default 6)")
    parser.add_argument("--all", action="store_true", help="also show step/epoch-style metadata")
    parser.add_argument("--json", action="store_true", help="emit the raw series as JSON (for exp report)")
    args = parser.parse_args()

    if args.json:
        # The report needs per-step raw values to plot, not segment means. Emit an
        # empty shell when there are no metrics, same as always.
        print(dump_json(args.run_dir))
        return 0

    series, source = collect(args.run_dir)
    if not series:
        print(f"no readable metrics found in {args.run_dir}.")
        print("looked for: *.jsonl, trainer_state.json, events.out.tfevents.*, *.log")
        print("if this method's metric format is unusual, write it a dedicated progress/<method>.py.")
        return 1

    render(series, source, args.segments, args.limit, args.all)
    return 0


if __name__ == "__main__":
    sys.exit(main())
