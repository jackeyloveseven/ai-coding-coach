# exptool — one entry point for training runs

`exp` collects the start / inspect / resume cycle for training runs into a single command. There's no magic in it. Two principles:

1. **Every command prints the command it actually runs first** (the grey `+ ssh ...`). Copy it, modify it, use it directly — once you're comfortable you don't need the tool.
2. **Read the trend, not the step.** Cut the run into segments and compare means, because single-step values jump around and carry no information.

This directory is the companion tooling for the [ai-coding-coach](../) skill. `references/training-run-literacy.md` in the skill covers the judgment; this is the execution entry point for that method.

> **This is the sanitized, generic build.** Hostnames, shared-disk paths and reward-service addresses all come from a config file — the repository holds only placeholders. Fill in your own environment.

---

## Quick start (runs locally; no cluster needed)

```bash
cd exptool
cp runs.conf.example runs.conf
./exp list              # you should see demo-sft
./exp status demo-sft   # look at the example run's progress
```

> If you downloaded a zip, `chmod +x exp` first. `git clone` preserves the executable bit, so it isn't needed there.

The machine column in `runs.conf.example` is `local`, meaning it runs on this machine and never goes over ssh. `examples/demo-sft/` is a fake run directory, there so you can see what the output looks like before wiring in anything real.

Pointing it at your own cluster:

```bash
mkdir -p ~/.config/exptool
cp exptool.conf.example ~/.config/exptool/config
cp runs.conf.example ~/.config/exptool/runs.conf
# edit both files with your own machines and runs
./exp list
```

`exp` itself can live in `~/bin`:

```bash
ln -s "$PWD/exp" ~/bin/exp
```

---

## Commands

| Command | What it does |
|---|---|
| `exp list` | Which runs are registered, and which are still going |
| `exp status [name]` | Progress, metric trend, health checks (defaults to the first registry row) |
| `exp log [name]` | Follow the log live (Ctrl+C to exit; the training keeps running) |
| `exp errors [name]` | Search for errors |
| `exp gpu <machine>` | See whether a machine's GPUs are free |
| `exp start <name>` | Start it (shows you the GPUs and asks before launching) |
| `exp stop <name>` | Stop it |
| `exp attach [name]` | Attach to the tmux session (exit with Ctrl+B then D) |
| `exp config [name]` | Print this run's `launch.sh` |
| `exp plan [name]` | Pre-registration: generates the template if absent, prints it if present |
| `exp report [name]` | Render a self-contained HTML report (curves + criterion line + health checks) |

---

## Registering runs: `runs.conf`

One run per line, six columns, separated by spaces or tabs. Lines starting with `#` and blank lines are ignored.

```
name             machine  dir                    method   tmux   note
demo-sft         local   ./examples/demo-sft    sft       -      example
hps-185          node-5  /shared/runs/awm_long  awm-hps   awm-1  long run, 400 steps
```

| Column | Meaning |
|---|---|
| name | Anything, as long as it's unique. `exp status` / `log` / `start` all use it |
| machine | A hostname `ssh` can reach; write `local` to run on this machine |
| dir | **Point at the individual run.** If one SFT experiment has both `smoke/` and `formal/` under it, write `formal/`, or the records from the two runs get mixed together |
| method | Decides which script reads progress — see the next section |
| tmux | Write `-` to say `exp start/stop` doesn't manage it (someone else started it, or it has finished) |
| note | Anything. Last field, so it may contain spaces |

---

## Pre-registration: `PLAN.md`

The six items to write before a run (hypothesis, control, variable, criterion, budget and stop-loss, prediction) live in a `PLAN.md` in the run directory, and `exp` reads it:

```bash
exp plan demo-sft     # generates the template if absent, prints it if present
```

The template looks like this:

```
Hypothesis: I think <the change> will improve <the metric>, because <the reason>
Control: the baseline is <what>, at the same budget, same data, same evaluation
Variable: this run changes only <one thing>
Criterion: judge by <metric>; it counts only if it moves past <how much> (decide now, not after seeing the result)
Budget and stop-loss: run for at most <how long>; stop early if <what happens>
Prediction: I expect <what>, confidence <high/medium/low>
```

Once it's filled in, `exp status` prints the **criterion** and the **prediction** directly above the metrics:

```
pre-registration
  criterion: judge by eval loss on the fixed dev set; it must come in at least 0.02 lower than the baseline
  prediction: I expect eval loss 0.01-0.03 lower, confidence medium
  (full text: exp plan demo-sft)
```

**Why this gets its own feature**: deciding "how much counts as an improvement" after the results are in will almost always produce "it improved". Putting the criterion next to the number forces you to check against the standard you set before the run, rather than hunting for a justification afterwards.

Field names accept both the full-width colon (`判据：`) and the ASCII one (`Criterion:`), and a leading `-` is allowed. The Chinese field names are still recognized, so existing PLAN files keep working. A missing `PLAN.md` doesn't block you — `status` just flags it.

---

## Progress readers

With a **method** column of `awm-hps`, `exp` looks for `progress/awm.py` — only the part before the `-`, so the rest is free for distinguishing reward models and the like. With no matching script it falls back to `progress/generic.py`.

That means `sft`, `dpo` and `diffusionnft` work with no code at all.

### `generic.py`

It looks for metrics in this order and uses the first source it finds:

| Source | Who writes it |
|---|---|
| `*.jsonl` (one JSON object per line) | your own training code, webtrainer, AWM |
| `trainer_state.json` | HuggingFace Trainer; TRL's SFT and DPO both write it |
| `events.out.tfevents.*` | tensorboard; requires tensorboard installed remotely |
| text in the log, such as `loss=0.12` or `reward: 0.5` | nearly every training script |

```bash
python3 progress/generic.py <run dir>
python3 progress/generic.py <run dir> --segments 10   # change the segment count (default 8)
python3 progress/generic.py <run dir> --limit 8       # show more metrics (default 6)
python3 progress/generic.py <run dir> --all           # also show step/epoch
python3 progress/generic.py <run dir> --json          # raw series as JSON (for exp report to plot)
```

The output looks like this:

```
source: metrics.jsonl | 64 points | 8 segments
metric                     1         2         3         4         5         6         7         8     change
grad_norm               1.45      1.11     0.893     0.717     0.596     0.512     0.462     0.394      -1.05
loss                    2.22      1.44     0.957     0.662     0.495     0.423     0.361      0.34      -1.88
lr                  1.87e-05  1.64e-05  1.41e-05  1.19e-05  9.57e-06  7.29e-06  5.00e-06  2.71e-06  -1.60e-05
rewards/accuracies     0.592      0.71     0.792     0.847     0.889     0.913      0.92     0.932       0.34
```

Names containing `loss`, `reward`, `acc`, `margin`, `grad`, `kl` or `lr` sort first. `step`/`epoch`-style metadata doesn't take a display slot by default (`--all` releases it).

### Writing a dedicated reader

You need one when the method's payoff can't be read off the training loss. RL-style methods are the usual case — the training reward changes prompts every step and swings wildly, so staring at it tells you nothing. What actually shows progress is the score on a **fixed eval set**.

Copy `progress/example.py`, rename it to `progress/<your method>.py`, and replace the file-reading part with your format. The convention is documented in the file header.

---

## Health checks

`exp status` looks at these:

- **Is the tmux session still there.** If not, run `exp errors` to see the failure.
- **Marker files** (looks for `FAILED` and `DONE` by default; configurable).
- **When the log last changed.** Over 30 minutes of silence may mean it's stuck on the reward service, on NCCL, or in a deadlock.
- **The reward service** (only checked when `REWARD_HEALTH_URL` is set). HTTP `200` or `401` both mean it's up (`401` just means no credentials were sent); `000` means no response.

---

## Reports: `exp report`

`exp status` is a plain-text table, but training curves are what graphs are for — reading them in a table is exactly the "staring at single steps" that `training-run-literacy.md` warns against. `exp report` renders one run as a **self-contained HTML file**:

```bash
exp report demo-sft                          # writes ./exp-report-demo-sft.html
exp report demo-sft --out ~/Desktop/look.html  # somewhere else
```

The report contains:

- **Run info**: name, machine, directory, method.
- **Pre-registration**: the **criterion** and **prediction** from `PLAN.md`. The criterion isn't just a line of text — wherever possible it becomes a **purple dashed line plus a pass zone** on the chart, putting the standard you set before the run in front of you at the moment you read the numbers. If it can recognize the metric and the value it draws the line; if not, it degrades to an **annotation band** above the chart rather than drawing something wrong.
- **Trend curves**: one inline SVG per metric — thin line is the raw per-step value, heavy dotted line is the segment mean, so the direction reads at a glance.
- **Segment means table**: the same 8-segment means as `exp status`.
- **Health checks**: the same logic as `exp status` (tmux, marker files, log freshness, reward service).

A few deliberate constraints:

- **Zero dependencies.** Python standard library only; the charts are hand-written inline SVG. No matplotlib, no jinja2. The repository's zero-dependency property holds.
- **Single self-contained file.** No external references at all — no CDN, no linked CSS/JS, no remote images. Offline, on a plane, or copied to someone else, it opens by double-click.
- **Outputs to the current directory**, not the run directory (which may be shared, read-only, or someone else's). Defaults to `./exp-report-<name>.html`; change it with `--out <path>` or `REPORT_DIR` in the config.
- Data comes from the **method-specific reader** (falling back to `generic.py`). A dedicated reader has to support `--json` to appear in the report (`generic.py` already does). Failing to recognize a metric doesn't stop the report — the criterion and health checks still come through.

Rendering happens locally (it reads and writes local files), which is why the config has an extra `LOCAL_PYTHON` entry (empty falls back to `REMOTE_PYTHON`).

---

## What's verified, and what isn't

This tool was rewritten from a working setup rather than extracted from a product, so the boundary is worth stating plainly.

**Exercised locally, with test coverage:**

- All of `progress/generic.py` — source priority, junk-data skipping, log-text parsing, segmentation, metric selection, and the `select_metrics` / `dump_json` paths that `exp report` reuses. 52 assertions, `python3 tests/test_generic.py`
- `exp list / status / config / plan / errors / report / help` end to end in `local` mode; reading and generating the pre-registration (including both full-width and ASCII colons); report generation (file written, each metric name and the `PLAN.md` criterion text present, criterion drawn as a reference line, defaulting to the current directory, no external URL anywhere); and the error paths (unknown command, unknown run, missing registry). 39 assertions, `bash tests/test_exp.sh`

**Not verified (no cluster to test against):**

- The ssh path (`run_on`'s remote branch, including `exp report` fetching the series remotely). The logic mirrors the local branch, but it has never been run for real.
- `exp start / stop / attach` — they depend on tmux and are only reached outside `local` mode.
- `exp gpu`'s `nvidia-smi` output parsing — written against the standard CSV format, never tried on a real GPU.
- Reading tensorboard event files — requires `tensorboard` to be installed to reach that path; not tested locally.
- The reward-service curl probe.
- `exp report`'s criterion parsing has only been tried on phrasings like the demo's ("at least 0.02 lower than the baseline"). Other phrasings that don't yield a recognizable metric or value degrade to an annotation band rather than drawing a wrong line — but they haven't been exercised either.
- The report has only been glanced at in Chrome (including `prefers-color-scheme` dark). Not checked in Firefox or Safari.

If any of these are wrong, the fix is a few lines — but try them on one machine first.

---

## Running the tests

```bash
python3 tests/test_generic.py    # the progress reader
bash    tests/test_exp.sh        # the exp command itself (local mode only)
```

On Windows, `python3` is often the Microsoft Store stub (it exits without doing anything). Use `py` instead:

```bash
py -X utf8 tests/test_generic.py
bash    tests/test_exp.sh        # this one detects the interpreter itself; nothing to configure
```
