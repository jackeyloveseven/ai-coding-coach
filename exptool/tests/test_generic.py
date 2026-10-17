#!/usr/bin/env python3
"""Unit tests for generic.py. Pure logic only: no cluster, no tensorboard.

Run it with:
  python3 tests/test_generic.py
"""

import importlib.util
import json
import math
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

spec = importlib.util.spec_from_file_location("generic", HERE.parent / "progress" / "generic.py")
generic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generic)

FAILURES = []


def same(got, want):
    """nan != nan, but here we want it to count as the same."""
    if isinstance(got, list) and isinstance(want, list):
        return len(got) == len(want) and all(same(a, b) for a, b in zip(got, want))
    if isinstance(got, float) and isinstance(want, float):
        return (math.isnan(got) and math.isnan(want)) or got == want
    return got == want


def check(label, got, want):
    if same(got, want):
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n       got:  {got!r}\n       want: {want!r}")
        FAILURES.append(label)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_source_priority():
    """jsonl beats trainer_state.json, which beats log text."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # All three sources present; jsonl should win
        write(root / "metrics.jsonl", '{"loss": 1.0}\n{"loss": 0.5}\n')
        write(root / "trainer_state.json", json.dumps({"log_history": [{"loss": 9.9}]}))
        write(root / "logs" / "train.log", "loss=8.8\n")
        series, source = generic.collect(root)
        check("picks jsonl when all three are present", source, "metrics.jsonl")
        check("reads the jsonl values", series["loss"], [1.0, 0.5])

        # Drop the jsonl; trainer_state.json should win
        (root / "metrics.jsonl").unlink()
        series, source = generic.collect(root)
        check("picks trainer_state.json when there is no jsonl", source, "trainer_state.json")
        check("takes values from log_history", series["loss"], [9.9])

        # Only the log left
        (root / "trainer_state.json").unlink()
        series, source = generic.collect(root)
        check("picks the log when it is all that is left", source, "1 log file(s)")
        check("takes values from log text", series["loss"], [8.8])


def test_jsonl_skips_junk():
    """Bad lines, non-numbers and bools all get skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(
            root / "metrics.jsonl",
            "\n".join(
                [
                    '{"loss": 1.0, "step": 1, "note": "hi", "flag": true, "nested": {"a": 1}}',
                    "this line is not JSON",
                    "",
                    '{"loss": 0.5, "step": 2}',
                ]
            )
            + "\n",
        )
        series, _ = generic.collect(root)
        check("only numeric fields: loss", series["loss"], [1.0, 0.5])
        check("numeric field: step", series["step"], [1.0, 2.0])
        check("skips string fields", "note" in series, False)
        check("skips bool fields", "flag" in series, False)
        check("skips nested dicts", "nested" in series, False)


def test_text_metric_regex():
    """Log-text forms: equals, colon, leading plus, scientific notation, underscore, slash."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(
            root / "logs" / "train.log",
            "step 100 loss=0.12 reward: 0.5 grad_norm = 1.2e-3 change=+0.3 rewards/accuracies=0.71\n",
        )
        series, _ = generic.collect(root)
        check("equals sign", series["loss"], [0.12])
        check("colon", series["reward"], [0.5])
        check("with spaces", series["grad_norm"], [0.0012])
        check("leading plus", series["change"], [0.3])
        check("name with a slash", series["rewards/accuracies"], [0.71])


def test_segments():
    check("4 segments", generic.segments([1, 2, 3, 4, 5, 6, 7, 8], 4), [1.5, 3.5, 5.5, 7.5])
    check("1 segment is the overall mean", generic.segments([1, 2, 3], 1), [2.0])
    check("cuts on the boundary when it does not divide evenly", generic.segments([1, 2, 3, 4, 5], 2), [1.5, 4.0])
    check("returns that many segments even when there are fewer points", len(generic.segments([1, 2], 4)), 4)
    check("empty series", generic.segments([], 4), [math.nan] * 4)

    # The real contract: when segments <= points, concatenating them gives back
    # the original series - no points dropped, no order changed
    values = [float(i) for i in range(1, 24)]
    for count in (1, 2, 3, 8, 23):
        segs = generic.segments(values, count)
        check(f"{count} segments drop no points", len(segs), count)
        check(
            f"{count} segments have the right means",
            [round(s, 6) for s in segs],
            [round(sum(values[i * 23 // count : (i + 1) * 23 // count]) / len(values[i * 23 // count : (i + 1) * 23 // count]), 6) for i in range(count)],
        )


def test_metric_preference_and_limit():
    """Names containing loss/reward/... sort first; 6 by default."""
    names = ["zzz", "step", "lr", "kl", "grad_norm", "margin", "acc", "loss", "reward"]
    ordered = sorted(names, key=generic.rank)
    check("preferred words sort first", ordered[:7], ["acc", "grad_norm", "kl", "loss", "lr", "margin", "reward"])
    check("6 by default", len(ordered[: generic.DEFAULT_LIMIT]), 6)


def test_select_metrics():
    """select_metrics is the metric-selection logic shared by render and exp report."""
    series = {"step": [1.0], "loss": [1.0], "zzz": [1.0]}
    check("drops metadata and sorts by rank", generic.select_metrics(series, limit=6), ["loss", "zzz"])
    check("limit takes effect", generic.select_metrics({"loss": [], "acc": [], "zzz": []}, limit=2), ["acc", "loss"])
    check("show_all keeps metadata", generic.select_metrics(series, limit=6, show_all=True), ["loss", "step", "zzz"])


def test_dump_json():
    """exp report relies on dump_json for per-step raw values."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(root / "metrics.jsonl", '{"loss": 1.0, "step": 1}\n{"loss": 0.5, "step": 2}\n')
        data = json.loads(generic.dump_json(root))
        check("json carries the source", data["source"], "metrics.jsonl")
        check("json carries the per-step series", data["series"]["loss"], [1.0, 0.5])
        check("json keeps step for the x axis", data["series"]["step"], [1.0, 2.0])


def test_fmt():
    check("ordinary decimal", generic.fmt(2.3145), "2.31")
    check("scientific notation for very small", generic.fmt(0.00012), "1.20e-04")
    check("scientific notation for very large", generic.fmt(1234567.0), "1.23e+06")
    check("nan", generic.fmt(math.nan), "nan")
    check("zero", generic.fmt(0.0), "0")


def test_render_smoke():
    """The whole render runs without blowing up, and segments are capped by points."""
    import io
    from contextlib import redirect_stdout

    series = {"loss": [1.0, 0.8, 0.6, 0.4], "step": [1.0, 2.0, 3.0, 4.0]}
    buf = io.StringIO()
    with redirect_stdout(buf):
        generic.render(series, "fixture", count=8, limit=6)
    out = buf.getvalue()
    check("segments are capped by points (4 points, at most 4 segments)", "4 segments" in out, True)
    check("lists loss", "loss" in out, True)


def test_render_skips_metadata():
    """step/epoch-style metadata doesn't take a display slot by default; --all releases it."""
    import io
    from contextlib import redirect_stdout

    series = {"step": [1.0, 2.0], "loss": [1.0, 0.5], "epoch": [0.0, 1.0], "num_steps": [4.0, 8.0]}

    def metric_names(text):
        # Line 0 is the source, line 1 the header; after that, the first field of
        # each line is the metric name
        return [line.split()[0] for line in text.splitlines()[2:] if line.split()]

    buf = io.StringIO()
    with redirect_stdout(buf):
        generic.render(series, "fixture", count=2, limit=6)
    out = buf.getvalue()
    check("step hidden by default", "step" in metric_names(out), False)
    check("epoch hidden by default", "epoch" in metric_names(out), False)
    check("loss still shown", "loss" in metric_names(out), True)
    check("whole-name matching only, so num_steps survives", "num_steps" in metric_names(out), True)

    buf = io.StringIO()
    with redirect_stdout(buf):
        generic.render(series, "fixture", count=2, limit=6, show_all=True)
    check("--all releases it", "step" in metric_names(buf.getvalue()), True)


def test_missing_dir():
    try:
        generic.collect(Path(tempfile.gettempdir()) / "definitely-not-here-12345")
    except SystemExit as exc:
        check("errors clearly when the directory does not exist", "not a directory" in str(exc), True)
    else:
        check("errors clearly when the directory does not exist", "did not exit", "should have exited")


def main():
    tests = [
        test_source_priority,
        test_jsonl_skips_junk,
        test_text_metric_regex,
        test_segments,
        test_metric_preference_and_limit,
        test_select_metrics,
        test_dump_json,
        test_fmt,
        test_render_smoke,
        test_render_skips_metadata,
        test_missing_dir,
    ]
    for test in tests:
        print(test.__name__)
        test()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} checks failed: {', '.join(FAILURES)}")
        return 1
    print("all passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
