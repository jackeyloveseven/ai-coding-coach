#!/usr/bin/env python3
"""把一次运行渲染成一份自包含的 HTML 报告 —— exp report 的后端。

为什么要有这个：训练曲线本来就是图的东西，硬用表格看，正是
references/training-run-literacy.md 里批评的「盯单步」。报告把曲线画出来，
并把 PLAN.md 里的**判据**标在图上（参考线 + 达标区），让读数的时候眼睛
被迫对照跑之前定下的标准。

只用标准库，图是手写的内联 SVG。整个文件没有任何外部引用——无 CDN、
无外链 CSS/JS、无外部图片，断网或拷给别人都能直接双击打开。

读数据的逻辑复用同目录的 generic.py（collect / select_metrics / segments / fmt），
不重写一遍。

一般由 exp report 调用，不直接手敲：
  report.py --out 报告.html --name demo-sft --machine local --dir <运行目录> \
            --method sft --series-json <序列.json> --plan <PLAN.md> --health <健康.tsv>
"""

import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import generic  # noqa: E402  （同目录，复用它的读数据逻辑）

# ---- 从判据文字里认指标、方向和数值 ---------------------------------------
NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")

# 「低」优先于「以上」：判据常写成「比 baseline 低 0.02 以上」，
# 这里的「以上」修饰的是幅度，方向仍是「低」。
LOWER_WORDS = ("低", "降", "小", "少", "以内", "以下", "不超过", "小于", "减少")
HIGHER_WORDS = ("高", "涨", "大", "多", "以上", "超过", "大于", "提升", "上升")

# PLAN 里写的是人话，指标名是代码里的键，中间靠这张别名表搭桥
ALIASES = {
    "acc": ("accuracy", "accuracies", "准确率", "准确度"),
    "margin": ("margin", "margins", "边界"),
    "grad_norm": ("grad_norm", "grad norm", "梯度"),
    "lr": ("lr", "learning rate", "学习率"),
    "loss": ("loss", "损失", "验证loss", "训练loss"),
    "reward": ("reward", "奖励"),
}


def esc(text):
    return html.escape(str(text), quote=True)


def plan_field(text, field):
    """从 PLAN.md 全文里取「字段：值」。全角/半角冒号都认，行首允许 - 或 *。"""
    for raw in text.splitlines():
        line = raw.strip().lstrip("-*").strip()
        for sep in ("：", ":"):
            if line.startswith(field + sep):
                return line.split(sep, 1)[1].strip()
    return ""


def _hit(token, low):
    """token 是否出现在 text（已小写）里。ASCII 词要求词边界，避免 lr 命中别处。"""
    if token.isascii():
        return re.search(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])", low) is not None
    return token in low


def match_metric(text, keys):
    """从判据文字里认出说的是哪个指标。认不出返回 None。"""
    low = text.lower()
    best = None  # (指标名, 命中的词长)
    for key in keys:
        if key.lower() in ("step", "epoch"):
            continue
        tokens = {key.lower()} | {p for p in re.split(r"[/_\s]+", key.lower()) if p}
        for alias, words in ALIASES.items():
            if alias in key.lower():
                tokens.update(w.lower() for w in words)
        for token in tokens:
            if len(token) >= 2 and _hit(token, low):
                if best is None or len(token) > best[1]:
                    best = (key, len(token))
    return best[0] if best else None


def parse_criterion(text, keys):
    """把判据一句话拆成 {指标, 方向, 数值, 是否相对 baseline}。拆不动也不报错。"""
    text = (text or "").strip()
    if not text:
        return None
    if any(w in text for w in LOWER_WORDS):
        direction = "lower"
    elif any(w in text for w in HIGHER_WORDS):
        direction = "higher"
    else:
        direction = None
    numbers = [float(n) for n in NUMBER_RE.findall(text)]
    return {
        "text": text,
        "metric": match_metric(text, keys),
        "direction": direction,
        "delta": numbers[-1] if numbers else None,
        "relative": ("baseline" in text.lower()) or ("比" in text),
    }


def criterion_line(crit, series):
    """把判据落成一条能画的绝对阈值线。落不下来（没指标/没数值/没方向）返回 None。"""
    if not crit or not crit["metric"] or crit["delta"] is None or not crit["direction"]:
        return None
    values = series.get(crit["metric"]) or []
    if not values:
        return None
    if crit["relative"]:
        # 「比 baseline 低 0.02」——baseline 的数值不在本次数据里，
        # 只能拿本次起点均值当参照，并在图上写明。
        head = values[: max(1, len(values) // 8)]
        base = sum(head) / len(head)
        value = base - crit["delta"] if crit["direction"] == "lower" else base + crit["delta"]
        note = f"以本次起点均值 {generic.fmt(base)} 为参照（PLAN 未给 baseline 数值）"
    else:
        value = crit["delta"]
        note = None
    return {"metric": crit["metric"], "value": value, "direction": crit["direction"], "note": note}


def svg_chart(name, values, steps, seg_count, line=None, width=760, height=210):
    """一个指标一张图：原始曲线（细）+ 分段均值（粗点线）+ 判据参考线/达标区。"""
    pad_l, pad_r, pad_t, pad_b = 62, 18, 16, 28
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    n = len(values)
    vmin, vmax = min(values), max(values)
    if line is not None:
        vmin, vmax = min(vmin, line["value"]), max(vmax, line["value"])
    if vmax == vmin:
        vmax = vmin + 1.0
    margin = (vmax - vmin) * 0.08
    vmin, vmax = vmin - margin, vmax + margin

    def x_at(i):
        return pad_l + (plot_w / 2 if n == 1 else i / (n - 1) * plot_w)

    def y_at(v):
        return pad_t + (1 - (v - vmin) / (vmax - vmin)) * plot_h

    out = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(name)} 趋势">']

    for k in range(5):
        value = vmin + (vmax - vmin) * k / 4
        y = y_at(value)
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" class="grid"/>')
        out.append(f'<text x="{pad_l - 8}" y="{y + 4:.1f}" class="tick tick-y">{esc(generic.fmt(value))}</text>')

    if line is not None:
        y = y_at(line["value"])
        if line["direction"] == "higher":
            zone = f'<rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{max(0.0, y - pad_t):.1f}" class="zone"/>'
        else:
            zone = f'<rect x="{pad_l}" y="{y:.1f}" width="{plot_w}" height="{max(0.0, pad_t + plot_h - y):.1f}" class="zone"/>'
        out.append(zone)
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" class="crit"/>')
        sign = "≥" if line["direction"] == "higher" else "≤"
        out.append(
            f'<text x="{width - pad_r - 4}" y="{y - 6:.1f}" class="tick crit-label">'
            f'判据 {sign} {esc(generic.fmt(line["value"]))}</text>'
        )

    raw = " ".join(f"{x_at(i):.1f},{y_at(v):.1f}" for i, v in enumerate(values))
    out.append(f'<polyline points="{raw}" class="raw"/>')

    count = max(1, min(seg_count, n))
    segs = generic.segments(values, count)
    centers = [((i * n // count) + ((i + 1) * n // count) - 1) / 2 for i in range(count)]
    smooth = " ".join(f"{x_at(c):.1f},{y_at(v):.1f}" for c, v in zip(centers, segs) if v == v)
    out.append(f'<polyline points="{smooth}" class="mean"/>')
    for c, v in zip(centers, segs):
        if v == v:
            out.append(f'<circle cx="{x_at(c):.1f}" cy="{y_at(v):.1f}" r="3.5" class="dot"/>')

    out.append(f'<circle cx="{x_at(n - 1):.1f}" cy="{y_at(values[-1]):.1f}" r="4" class="dot"/>')
    out.append(
        f'<text x="{x_at(n - 1) - 2:.1f}" y="{y_at(values[-1]) - 10:.1f}" class="tick end-label">'
        f'{esc(generic.fmt(values[-1]))}</text>'
    )

    first = steps[0] if steps else 1
    last = steps[-1] if steps else n
    out.append(f'<text x="{pad_l}" y="{height - 8}" class="tick">step {esc(generic.fmt(first))}</text>')
    out.append(
        f'<text x="{width - pad_r}" y="{height - 8}" class="tick" text-anchor="end">'
        f'step {esc(generic.fmt(last))}</text>'
    )
    out.append("</svg>")
    return "".join(out)


CSS = """
:root{color-scheme:light;--plane:#f9f9f7;--surface-1:#fcfcfb;--text-primary:#0b0b0b;
--text-secondary:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--raw:#898781;
--series-1:#2a78d6;--crit:#6250d6;--good:#0ca30c;--warn:#d03b3b;--border:rgba(11,11,11,.10)}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;
--plane:#0d0d0d;--surface-1:#1a1a19;--text-primary:#f0efec;--text-secondary:#c3c2b7;
--muted:#898781;--grid:#2c2c2a;--axis:#383835;--raw:#898781;--series-1:#3987e5;
--crit:#9085e9;--good:#0ca30c;--warn:#e66767;--border:rgba(255,255,255,.10)}}
:root[data-theme="dark"]{color-scheme:dark;--plane:#0d0d0d;--surface-1:#1a1a19;
--text-primary:#f0efec;--text-secondary:#c3c2b7;--muted:#898781;--grid:#2c2c2a;
--axis:#383835;--raw:#898781;--series-1:#3987e5;--crit:#9085e9;--good:#0ca30c;
--warn:#e66767;--border:rgba(255,255,255,.10)}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--text-primary);
font:15px/1.6 system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
main{max-width:840px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:24px;margin:0 0 4px}
h2{font-size:16px;margin:36px 0 12px;color:var(--text-primary)}
.meta{color:var(--text-secondary);font-size:13px;margin:0}
.meta b{color:var(--text-primary);font-weight:600}
.band{display:flex;gap:12px;align-items:flex-start;background:color-mix(in srgb,var(--crit) 8%,var(--surface-1));
border-left:4px solid var(--crit);border-radius:6px;padding:12px 14px;margin:0 0 10px}
.band.empty{background:var(--surface-1);border-left-color:var(--axis)}
.band-tag{flex:none;font-weight:700;color:var(--crit);font-size:13px;padding-top:1px}
.band.empty .band-tag{color:var(--muted)}
.band-text{white-space:pre-wrap}
.band-note{color:var(--text-secondary);font-size:13px;margin:0 0 14px 16px}
.legend{color:var(--text-secondary);font-size:13px;margin:0 0 16px}
.legend .k{display:inline-block;width:22px;height:0;border-top-width:3px;border-top-style:solid;
vertical-align:middle;margin:0 4px 0 14px}
.legend .k:first-child{margin-left:0}
.raw-k{border-top-color:var(--raw)}
.mean-k{border-top-color:var(--series-1)}
.crit-k{border-top-style:dashed;border-top-color:var(--crit)}
figure.chart{margin:0 0 22px;background:var(--surface-1);border:1px solid var(--border);
border-radius:8px;padding:12px 14px 6px}
figcaption{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px}
.c-name{font-weight:600;font-family:ui-monospace,Menlo,Consolas,monospace}
.c-change{color:var(--text-secondary);font-size:13px;font-variant-numeric:tabular-nums}
svg{display:block;width:100%;height:auto}
.grid{stroke:var(--grid);stroke-width:1}
.raw{fill:none;stroke:var(--raw);stroke-width:1.5;stroke-linejoin:round;stroke-linecap:round;opacity:.6}
.mean{fill:none;stroke:var(--series-1);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.dot{fill:var(--series-1);stroke:var(--surface-1);stroke-width:2}
.crit{stroke:var(--crit);stroke-width:2;stroke-dasharray:6 4}
.zone{fill:var(--crit);opacity:.08}
.tick{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.tick-y{text-anchor:end}
.crit-label{fill:var(--text-secondary);text-anchor:end;font-weight:600}
.end-label{fill:var(--text-secondary);text-anchor:end}
table.seg{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
table.seg th,table.seg td{padding:6px 8px;text-align:right;border-bottom:1px solid var(--grid)}
table.seg thead th{color:var(--text-secondary);font-weight:600}
table.seg .row-name{text-align:left;font-family:ui-monospace,Menlo,Consolas,monospace;font-weight:600}
table.seg .chg{color:var(--text-secondary)}
ul.health{list-style:none;margin:0;padding:0}
ul.health li{display:flex;gap:8px;padding:5px 0;border-bottom:1px solid var(--grid)}
.h-dot{flex:none;width:9px;height:9px;border-radius:50%;margin-top:7px;background:var(--muted)}
.h-ok .h-dot{background:var(--good)}
.h-warn .h-dot{background:var(--warn)}
.h-label{flex:none;min-width:150px;color:var(--text-secondary)}
.h-value{white-space:pre-wrap}
.empty{color:var(--text-secondary)}
footer{margin-top:40px;color:var(--muted);font-size:12px;border-top:1px solid var(--grid);padding-top:12px}
"""


def read_text(path):
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def build_html(*, name, machine, run_dir, method, source, series, plan_text, health,
               segments_count, limit, show_all, generated_at):
    keys = list(series)
    metrics = generic.select_metrics(series, limit, show_all)
    steps = series.get("step") or []
    points = max((len(v) for v in series.values()), default=0)
    seg_count = max(1, min(segments_count, points)) if points else segments_count

    crit_text = plan_field(plan_text, "判据")
    pred_text = plan_field(plan_text, "预测")
    criterion = parse_criterion(crit_text, keys)
    crit_line = criterion_line(criterion, series)

    # 判据标注带：无论能不能落成阈值线，判据本身都要摆在图的正上方
    if crit_text:
        band = (
            '<div class="band"><div class="band-tag">判据</div>'
            f'<div class="band-text">{esc(crit_text)}</div></div>'
        )
        if crit_line:
            sign = "≥" if crit_line["direction"] == "higher" else "≤"
            value = f'<b>{esc(crit_line["metric"])} {sign} {esc(generic.fmt(crit_line["value"]))}</b>'
            if crit_line["note"]:
                # 参照是从本次数据里取的，不是 PLAN 里的原始判据。话得说清楚：
                # 把「按判据推出来的线」说成「判据本身」，正是这个仓库要防的那件事。
                band += (
                    f'<p class="band-note">图上那条紫色虚线是按这条判据<em>推出来</em>的参考线：'
                    f'{value}，{esc(crit_line["note"])}。紫色阴影是达标区。'
                    f'它不是判据本身，读数仍以 PLAN 里那句为准。</p>'
                )
            else:
                band += (
                    f'<p class="band-note">图上那条紫色虚线就是这条判据：'
                    f'{value}。紫色阴影是达标区。</p>'
                )
        else:
            band += '<p class="band-note">这条判据认不出可画的指标或数值，所以只作为标注带放在这里。</p>'
    else:
        band = (
            '<div class="band empty"><div class="band-tag">判据</div>'
            '<div class="band-text">（没写）—— 这是最容易被跳过、也最要紧的一项。'
            '跑之前用 exp plan 补上。</div></div>'
        )

    pred = (
        f'<div class="band"><div class="band-tag">预测</div>'
        f'<div class="band-text">{esc(pred_text)}</div></div>'
        if pred_text else
        '<p class="empty">（预测：没写）</p>'
    )

    # 健康检查
    rows = []
    for raw in health.splitlines():
        if not raw.strip():
            continue
        fields = raw.split("\t")
        status, label, value = (fields + ["", "", raw])[:3] if len(fields) < 3 else fields[:3]
        rows.append(
            f'<li class="h-{esc(status)}"><span class="h-dot"></span>'
            f'<span class="h-label">{esc(label)}</span><span class="h-value">{esc(value)}</span></li>'
        )
    health_html = f'<ul class="health">{"".join(rows)}</ul>' if rows else '<p class="empty">（没做健康检查）</p>'

    # 曲线
    if metrics:
        charts = []
        for metric in metrics:
            values = series[metric]
            count = max(1, min(segments_count, len(values)))
            segs = generic.segments(values, count)
            change = segs[-1] - segs[0]
            line = crit_line if (crit_line and crit_line["metric"] == metric) else None
            charts.append(
                '<figure class="chart">'
                f'<figcaption><span class="c-name">{esc(metric)}</span>'
                f'<span class="c-change">变化 {esc(generic.fmt(change))}</span></figcaption>'
                f'{svg_chart(metric, values, steps if len(steps) == len(values) else [], count, line)}'
                '</figure>'
            )
        charts_html = "".join(charts)
        legend = (
            '<p class="legend"><span class="k raw-k"></span>逐步原始值'
            '<span class="k mean-k"></span>分段均值'
            '<span class="k crit-k"></span>判据参考线</p>'
        )
    else:
        charts_html = '<p class="empty">这个目录里没找到可读的指标。找过 *.jsonl、trainer_state.json、events.out.tfevents.*、*.log。</p>'
        legend = ""

    # 分段均值表
    if metrics:
        head = "".join(f"<th>{i + 1}</th>" for i in range(seg_count))
        body = []
        for metric in metrics:
            segs = generic.segments(series[metric], seg_count)
            cells = "".join(f"<td>{esc(generic.fmt(v))}</td>" for v in segs)
            body.append(
                f'<tr><th class="row-name">{esc(metric)}</th>{cells}'
                f'<td class="chg">{esc(generic.fmt(segs[-1] - segs[0]))}</td></tr>'
            )
        table = (
            f'<table class="seg"><thead><tr><th>指标</th>{head}<th>变化</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>'
        )
        source_note = f'来源: {esc(source)} ｜ 共 {points} 个点 ｜ 切 {seg_count} 段'
    else:
        table = ""
        source_note = ""

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>实验报告 · {esc(name)}</title>
<style>{CSS}</style>
</head>
<body>
<main>
<h1>{esc(name)} 实验报告</h1>
<p class="meta">机器 <b>{esc(machine)}</b> ｜ 方法 <b>{esc(method)}</b> ｜ 目录 <b>{esc(run_dir)}</b> ｜ 生成于 {esc(generated_at)}</p>

<h2>事前记录</h2>
{band}
{pred}

<h2>健康检查</h2>
{health_html}

<h2>趋势曲线</h2>
{legend}
{charts_html}

<h2>分段均值（{seg_count} 段）</h2>
<p class="meta">{esc(source_note)}</p>
{table}

<footer>由 exp report 生成 ｜ 单文件自包含，无外部引用，可离线打开</footer>
</main>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="把一次运行渲染成自包含的 HTML 报告")
    parser.add_argument("--out", required=True, help="报告写到哪里")
    parser.add_argument("--name", default="")
    parser.add_argument("--machine", default="")
    parser.add_argument("--dir", dest="run_dir", default="")
    parser.add_argument("--method", default="")
    parser.add_argument("--series-json", default="", help="generic.py --json 的输出文件")
    parser.add_argument("--plan", default="", help="PLAN.md 全文")
    parser.add_argument("--health", default="", help="健康检查 TSV（状态<TAB>标签<TAB>值）")
    parser.add_argument("--segments", type=int, default=generic.DEFAULT_SEGMENTS)
    parser.add_argument("--limit", type=int, default=generic.DEFAULT_LIMIT)
    parser.add_argument("--all", action="store_true", help="连 step/epoch 这类元数据也画")
    args = parser.parse_args()

    series, source = {}, None
    if args.series_json:
        try:
            data = json.loads(read_text(args.series_json))
            series = data.get("series") or {}
            source = data.get("source")
        except (json.JSONDecodeError, AttributeError):
            print(f"读不了序列 JSON：{args.series_json}（读取器可能不支持 --json）", file=sys.stderr)

    doc = build_html(
        name=args.name or "(未命名)",
        machine=args.machine,
        run_dir=args.run_dir,
        method=args.method,
        source=source,
        series=series,
        plan_text=read_text(args.plan),
        health=read_text(args.health),
        segments_count=args.segments,
        limit=args.limit,
        show_all=args.all,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    out = Path(args.out)
    if out.parent and not out.parent.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
