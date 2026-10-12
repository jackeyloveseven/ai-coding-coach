#!/usr/bin/env python3
"""generic.py 的单元测试。只测纯逻辑，不需要集群、不需要 tensorboard。

跑法：
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
    """nan 不等于 nan，但这里我们想让它算「一样」。"""
    if isinstance(got, list) and isinstance(want, list):
        return len(got) == len(want) and all(same(a, b) for a, b in zip(got, want))
    if isinstance(got, float) and isinstance(want, float):
        return (math.isnan(got) and math.isnan(want)) or got == want
    return got == want


def check(label, got, want):
    if same(got, want):
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n       得到: {got!r}\n       期望: {want!r}")
        FAILURES.append(label)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_source_priority():
    """jsonl 优先于 trainer_state.json，优先于日志文字。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # 三个来源都在，应该选 jsonl
        write(root / "metrics.jsonl", '{"loss": 1.0}\n{"loss": 0.5}\n')
        write(root / "trainer_state.json", json.dumps({"log_history": [{"loss": 9.9}]}))
        write(root / "logs" / "train.log", "loss=8.8\n")
        series, source = generic.collect(root)
        check("三个来源都在时选 jsonl", source, "metrics.jsonl")
        check("读的是 jsonl 的值", series["loss"], [1.0, 0.5])

        # 去掉 jsonl，应该选 trainer_state.json
        (root / "metrics.jsonl").unlink()
        series, source = generic.collect(root)
        check("没有 jsonl 时选 trainer_state.json", source, "trainer_state.json")
        check("从 log_history 取值", series["loss"], [9.9])

        # 只剩日志
        (root / "trainer_state.json").unlink()
        series, source = generic.collect(root)
        check("只剩日志时选日志", source, "1 个日志文件")
        check("从日志文字取值", series["loss"], [8.8])


def test_jsonl_skips_junk():
    """坏行、非数字、bool 都要跳过。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(
            root / "metrics.jsonl",
            "\n".join(
                [
                    '{"loss": 1.0, "step": 1, "note": "hi", "flag": true, "nested": {"a": 1}}',
                    "这一行不是 JSON",
                    "",
                    '{"loss": 0.5, "step": 2}',
                ]
            )
            + "\n",
        )
        series, _ = generic.collect(root)
        check("只收数字字段 loss", series["loss"], [1.0, 0.5])
        check("收数字字段 step", series["step"], [1.0, 2.0])
        check("跳过字符串字段", "note" in series, False)
        check("跳过 bool 字段", "flag" in series, False)
        check("跳过嵌套字典", "nested" in series, False)


def test_text_metric_regex():
    """日志文字的写法：等号、冒号、正号、科学计数法、下划线、斜杠。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(
            root / "logs" / "train.log",
            "step 100 loss=0.12 reward: 0.5 grad_norm = 1.2e-3 change=+0.3 rewards/accuracies=0.71\n",
        )
        series, _ = generic.collect(root)
        check("等号", series["loss"], [0.12])
        check("冒号", series["reward"], [0.5])
        check("带空格", series["grad_norm"], [0.0012])
        check("正号", series["change"], [0.3])
        check("带斜杠的名字", series["rewards/accuracies"], [0.71])


def test_segments():
    check("切 4 段", generic.segments([1, 2, 3, 4, 5, 6, 7, 8], 4), [1.5, 3.5, 5.5, 7.5])
    check("切 1 段就是整体平均", generic.segments([1, 2, 3], 1), [2.0])
    check("不整除时按边界切", generic.segments([1, 2, 3, 4, 5], 2), [1.5, 4.0])
    check("段数多于点数时也返回这么多段", len(generic.segments([1, 2], 4)), 4)
    check("空序列", generic.segments([], 4), [math.nan] * 4)

    # 真正的契约：段数不超过点数时，各段拼起来就是原序列——不丢点、不改顺序
    values = [float(i) for i in range(1, 24)]
    for count in (1, 2, 3, 8, 23):
        segs = generic.segments(values, count)
        check(f"切 {count} 段不丢点", len(segs), count)
        check(
            f"切 {count} 段均值正确",
            [round(s, 6) for s in segs],
            [round(sum(values[i * 23 // count : (i + 1) * 23 // count]) / len(values[i * 23 // count : (i + 1) * 23 // count]), 6) for i in range(count)],
        )


def test_metric_preference_and_limit():
    """带 loss/reward/... 的排前面，默认最多 6 个。"""
    names = ["zzz", "step", "lr", "kl", "grad_norm", "margin", "acc", "loss", "reward"]
    ordered = sorted(names, key=generic.rank)
    check("优先词排在前面", ordered[:7], ["acc", "grad_norm", "kl", "loss", "lr", "margin", "reward"])
    check("默认只取 6 个", len(ordered[: generic.DEFAULT_LIMIT]), 6)


def test_select_metrics():
    """select_metrics 是 render 和 exp report 共用的选指标逻辑。"""
    series = {"step": [1.0], "loss": [1.0], "zzz": [1.0]}
    check("滤掉元数据并按 rank 排序", generic.select_metrics(series, limit=6), ["loss", "zzz"])
    check("limit 生效", generic.select_metrics({"loss": [], "acc": [], "zzz": []}, limit=2), ["acc", "loss"])
    check("show_all 时不滤元数据", generic.select_metrics(series, limit=6, show_all=True), ["loss", "step", "zzz"])


def test_dump_json():
    """exp report 靠 dump_json 拿逐步原始值。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(root / "metrics.jsonl", '{"loss": 1.0, "step": 1}\n{"loss": 0.5, "step": 2}\n')
        data = json.loads(generic.dump_json(root))
        check("json 里带来源", data["source"], "metrics.jsonl")
        check("json 里带逐步序列", data["series"]["loss"], [1.0, 0.5])
        check("json 保留 step 供画横轴", data["series"]["step"], [1.0, 2.0])


def test_fmt():
    check("普通小数", generic.fmt(2.3145), "2.31")
    check("很小用科学计数法", generic.fmt(0.00012), "1.20e-04")
    check("很大用科学计数法", generic.fmt(1234567.0), "1.23e+06")
    check("nan", generic.fmt(math.nan), "nan")
    check("零", generic.fmt(0.0), "0")


def test_render_smoke():
    """整体渲染不崩，且段数受点数限制。"""
    import io
    from contextlib import redirect_stdout

    series = {"loss": [1.0, 0.8, 0.6, 0.4], "step": [1.0, 2.0, 3.0, 4.0]}
    buf = io.StringIO()
    with redirect_stdout(buf):
        generic.render(series, "fixture", count=8, limit=6)
    out = buf.getvalue()
    check("段数被点数截住（4 个点最多 4 段）", "切 4 段" in out, True)
    check("列出了 loss", "loss" in out, True)


def test_render_skips_metadata():
    """step/epoch 这类元数据默认不占显示位，--all 时再放出来。"""
    import io
    from contextlib import redirect_stdout

    series = {"step": [1.0, 2.0], "loss": [1.0, 0.5], "epoch": [0.0, 1.0], "num_steps": [4.0, 8.0]}

    def metric_names(text):
        # 第 0 行是「来源」，第 1 行是表头，之后每行的第一个字段是指标名
        return [line.split()[0] for line in text.splitlines()[2:] if line.split()]

    buf = io.StringIO()
    with redirect_stdout(buf):
        generic.render(series, "fixture", count=2, limit=6)
    out = buf.getvalue()
    check("默认不显示 step", "step" in metric_names(out), False)
    check("默认不显示 epoch", "epoch" in metric_names(out), False)
    check("仍然显示 loss", "loss" in metric_names(out), True)
    check("只做整名匹配，num_steps 保留", "num_steps" in metric_names(out), True)

    buf = io.StringIO()
    with redirect_stdout(buf):
        generic.render(series, "fixture", count=2, limit=6, show_all=True)
    check("--all 时放出来", "step" in metric_names(buf.getvalue()), True)


def test_missing_dir():
    try:
        generic.collect(Path(tempfile.gettempdir()) / "definitely-not-here-12345")
    except SystemExit as exc:
        check("目录不存在时明确报错", "不是目录" in str(exc), True)
    else:
        check("目录不存在时明确报错", "没有退出", "应该退出")


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
        print(f"{len(FAILURES)} 项没过：{', '.join(FAILURES)}")
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
