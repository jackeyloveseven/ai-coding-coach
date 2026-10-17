#!/usr/bin/env python3
"""Render one run as a self-contained HTML report - the backend for exp report.

Why this exists: training curves are what graphs are for. Reading them in a table
is exactly the "staring at single steps" that references/training-run-literacy.md
warns against. The report draws the curves and marks the **criterion** from
PLAN.md on them (reference line plus pass zone), so reading the numbers forces
your eye against the standard you set before the run.

Standard library only; the charts are hand-written inline SVG. The whole file has
no external references - no CDN, no linked CSS/JS, no remote images - so it opens
by double-click, offline, or after being copied to someone else.

The data reading reuses generic.py from the same directory (collect /
select_metrics / segments / fmt) rather than reimplementing it.

Normally invoked by exp report rather than typed by hand:
  report.py --out report.html --name demo-sft --machine local --dir <run dir> \\
            --method sft --series-json <series.json> --plan <PLAN.md> --health <health.tsv>
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

import generic  # noqa: E402  (same directory; reuse its data reading)

# ---- recognize the metric, direction and value in a criterion sentence ------
NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")

# "lower" is checked before "above": a criterion is often phrased as "more than
# 0.02 lower than the baseline", where "more than" modifies the magnitude while
# the direction is still "lower". Chinese wording is kept alongside the English
# so existing PLAN.md files in Chinese keep working.
LOWER_WORDS = ("低", "降", "小", "少", "以内", "以下", "不超过", "小于", "减少",
               "lower", "less", "below", "under", "smaller", "decrease", "decreased",
               "reduce", "reduced", "within", "at most", "no more than", "drop", "drops")
HIGHER_WORDS = ("高", "涨", "大", "多", "以上", "超过", "大于", "提升", "上升",
                "higher", "above", "over", "greater", "larger", "increase", "increased",
                "improve", "improved", "exceed", "exceeds", "at least", "no less than",
                "gain", "gains")

# The PLAN is written in prose; metric names are keys in the code. This table
# bridges the two.
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


def plan_field(text, fields):
    """Pull "field: value" out of the full PLAN.md text. Accepts both the
    full-width and the ASCII colon; a leading - or * is allowed. `fields` is a
    single name or a tuple of accepted names."""
    if isinstance(fields, str):
        fields = (fields,)
    for raw in text.splitlines():
        line = raw.strip().lstrip("-*").strip()
        for field in fields:
            for sep in ("：", ":"):
                if line.startswith(field + sep):
                    return line.split(sep, 1)[1].strip()
    return ""


def _hit(token, low):
    """Whether token appears in text (already lowercased). ASCII words require a
    word boundary, so lr doesn't match somewhere in the middle of another word."""
    if token.isascii():
        return re.search(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])", low) is not None
    return token in low


def match_metric(text, keys):
    """Work out which metric the criterion is talking about. None if unrecognized."""
    low = text.lower()
    best = None  # (metric name, length of the matched token)
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
    """Split a criterion sentence into {metric, direction, value, relative to
    baseline}. Returns quietly when it can't be split."""
    text = (text or "").strip()
    if not text:
        return None
    low = text.lower()
    if any(w in low for w in LOWER_WORDS):
        direction = "lower"
    elif any(w in low for w in HIGHER_WORDS):
        direction = "higher"
    else:
        direction = None
    numbers = [float(n) for n in NUMBER_RE.findall(text)]
    return {
        "text": text,
        "metric": match_metric(text, keys),
        "direction": direction,
        "delta": numbers[-1] if numbers else None,
        "relative": ("baseline" in low) or ("比" in text) or (" than " in low)
                    or (" vs " in low) or ("relative to" in low),
    }


def criterion_line(crit, series):
    """Turn the criterion into an absolute threshold line that can be drawn.
    Returns None when it can't be pinned down (no metric / no number / no
    direction)."""
    if not crit or not crit["metric"] or crit["delta"] is None or not crit["direction"]:
        return None
    values = series.get(crit["metric"]) or []
    if not values:
        return None
    if crit["relative"]:
        # "0.02 lower than the baseline" - the baseline's own value isn't in this
        # data, so the run's own starting mean stands in for it, and the chart
        # says so.
        head = values[: max(1, len(values) // 8)]
        base = sum(head) / len(head)
        value = base - crit["delta"] if crit["direction"] == "lower" else base + crit["delta"]
        note = f"using this run's starting mean {generic.fmt(base)} as the reference (the PLAN gives no baseline value)"
    else:
        value = crit["delta"]
        note = None
    return {"metric": crit["metric"], "value": value, "direction": crit["direction"], "note": note}


def svg_chart(name, values, steps, seg_count, line=None, width=760, height=210):
    """One chart per metric: raw curve (thin) + segment means (heavy dotted) +
    criterion reference line and pass zone."""
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

    out = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(name)} trend">']

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
            f'criterion {sign} {esc(generic.fmt(line["value"]))}</text>'
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

    crit_text = plan_field(plan_text, ("Criterion", "判据"))
    pred_text = plan_field(plan_text, ("Prediction", "预测"))
    criterion = parse_criterion(crit_text, keys)
    crit_line = criterion_line(criterion, series)

    # Criterion band: whether or not it resolves to a threshold line, the
    # criterion itself belongs directly above the charts.
    if crit_text:
        band = (
            '<div class="band"><div class="band-tag">criterion</div>'
            f'<div class="band-text">{esc(crit_text)}</div></div>'
        )
        if crit_line:
            sign = "≥" if crit_line["direction"] == "higher" else "≤"
            value = f'<b>{esc(crit_line["metric"])} {sign} {esc(generic.fmt(crit_line["value"]))}</b>'
            if crit_line["note"]:
                # The reference was taken from this run's own data, not from the
                # PLAN. Say so plainly: passing off a line derived from the
                # criterion as the criterion itself is exactly what this repo
                # exists to prevent.
                band += (
                    f'<p class="band-note">The purple dashed line on the chart is a reference line '
                    f'<em>derived</em> from this criterion: {value}, {esc(crit_line["note"])}. '
                    f'The purple shading is the pass zone. It is not the criterion itself - '
                    f'reading still goes by what the PLAN says.</p>'
                )
            else:
                band += (
                    f'<p class="band-note">The purple dashed line on the chart is this criterion: '
                    f'{value}. The purple shading is the pass zone.</p>'
                )
        else:
            band += '<p class="band-note">No plottable metric or value could be recognized in this criterion, so it appears as an annotation band only.</p>'
    else:
        band = (
            '<div class="band empty"><div class="band-tag">criterion</div>'
            '<div class="band-text">(not written) - the item most often skipped, and the one that '
            'matters most. Fill it in before the run with exp plan.</div></div>'
        )

    pred = (
        f'<div class="band"><div class="band-tag">prediction</div>'
        f'<div class="band-text">{esc(pred_text)}</div></div>'
        if pred_text else
        '<p class="empty">(prediction: not written)</p>'
    )

    # health checks
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
    health_html = f'<ul class="health">{"".join(rows)}</ul>' if rows else '<p class="empty">(no health checks)</p>'

    # charts
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
                f'<span class="c-change">change {esc(generic.fmt(change))}</span></figcaption>'
                f'{svg_chart(metric, values, steps if len(steps) == len(values) else [], count, line)}'
                '</figure>'
            )
        charts_html = "".join(charts)
        legend = (
            '<p class="legend"><span class="k raw-k"></span>raw per-step'
            '<span class="k mean-k"></span>segment mean'
            '<span class="k crit-k"></span>criterion line</p>'
        )
    else:
        charts_html = '<p class="empty">No readable metrics found in this directory. Looked for *.jsonl, trainer_state.json, events.out.tfevents.*, *.log.</p>'
        legend = ""

    # segment means table
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
            f'<table class="seg"><thead><tr><th>metric</th>{head}<th>change</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>'
        )
        source_note = f'source: {esc(source)} | {points} points | {seg_count} segments'
    else:
        table = ""
        source_note = ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Run report · {esc(name)}</title>
<style>{CSS}</style>
</head>
<body>
<main>
<h1>{esc(name)} run report</h1>
<p class="meta">machine <b>{esc(machine)}</b> | method <b>{esc(method)}</b> | dir <b>{esc(run_dir)}</b> | generated {esc(generated_at)}</p>

<h2>Pre-registration</h2>
{band}
{pred}

<h2>Health checks</h2>
{health_html}

<h2>Trend</h2>
{legend}
{charts_html}

<h2>Segment means ({seg_count} segments)</h2>
<p class="meta">{esc(source_note)}</p>
{table}

<footer>Generated by exp report | single self-contained file, no external references, opens offline</footer>
</main>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Render one run as a self-contained HTML report")
    parser.add_argument("--out", required=True, help="where to write the report")
    parser.add_argument("--name", default="")
    parser.add_argument("--machine", default="")
    parser.add_argument("--dir", dest="run_dir", default="")
    parser.add_argument("--method", default="")
    parser.add_argument("--series-json", default="", help="the file written by generic.py --json")
    parser.add_argument("--plan", default="", help="the full PLAN.md text")
    parser.add_argument("--health", default="", help="health check TSV (status<TAB>label<TAB>value)")
    parser.add_argument("--segments", type=int, default=generic.DEFAULT_SEGMENTS)
    parser.add_argument("--limit", type=int, default=generic.DEFAULT_LIMIT)
    parser.add_argument("--all", action="store_true", help="also chart step/epoch-style metadata")
    args = parser.parse_args()

    series, source = {}, None
    if args.series_json:
        try:
            data = json.loads(read_text(args.series_json))
            series = data.get("series") or {}
            source = data.get("source")
        except (json.JSONDecodeError, AttributeError):
            print(f"cannot read the series JSON: {args.series_json} (the reader may not support --json)", file=sys.stderr)

    doc = build_html(
        name=args.name or "(unnamed)",
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
