# ai-coding-coach

[![tests](https://github.com/jackeyloveseven/ai-coding-coach/actions/workflows/test.yml/badge.svg?branch=pro)](https://github.com/jackeyloveseven/ai-coding-coach/actions/workflows/test.yml?query=branch%3Apro)

> **You are on the `pro` branch.** This is the Community edition plus the tooling — `exptool/` and `scripts/ledger.py`. The Community edition on its own is the `main` branch. Covered by [LICENSE-COMMERCIAL](LICENSE-COMMERCIAL).

> **Writes code with you, and turns you into an engineer who can see at a glance where the AI got it wrong.**

For early- and mid-career ML engineers. The goal isn't to type faster than the AI. It's to be able to **review** the AI.

Landing page: <https://jackeyloveseven.github.io/ai-coding-coach/>

```
/plugin install ai-coding-coach --marketplace jackeyloveseven/ai-coding-coach
```

<sub>Other install methods are under [Install](#install).</sub>

---

## What it looks like

**🟡 Yellow tier** — you paste an evaluation script for me to fix. When I'm done, a *Read-it checkpoint* comes attached:

> - **Key lines**: `model.eval()` and `torch.no_grad()` are both required. Drop `eval()` and dropout and BatchNorm stay in training mode, so your metric gets noisier and reads low — and **nothing errors**.
> - **Silent risk**: `total += batch_loss` never multiplies by batch size, so dividing by `len(loader)` gives you a *per-batch* average. It skews when the last batch is short. Verify: compare against `total loss / total samples`.
> - **Predict first**: when this finishes, how far apart will `val_loss` be from `train_loss` over the last few steps?
> - **Self-check**: delete `model.eval()`. Does the metric get better or worse? Why?

**🔴 Red tier** — you want to implement the DPO loss yourself. I don't give you the answer. I give you scaffolding:

> Write a version, then we'll compare:
>
> ```python
> def dpo_loss(policy_logps, ref_logps, chosen, rejected, beta=0.1):
>     """Returns (loss, chosen_rewards, rejected_rewards).
>     When you're done, check against the official implementation with torch.allclose."""
> ```
>
> One hint: `beta` should appear **twice** in this implementation. Work out why each time.

Want the answer directly? Say "**just give it**" and you get it immediately, no follow-up questions.

---

## Why this exists: four failure modes

Writing code is depreciating fast. Judgment isn't. These are the four ways early-career ML engineers trip in the AI era — and everything in this repo points at one of them.

### #1 It runs, but the result is quietly wrong

**The problem**: the most expensive bug in this line of work isn't the one that throws. It's the one that **runs, prints a metric, and is wrong**. Train and eval get reversed. The metric is computed on augmented data. The loss accumulates without dividing by the right sample count. Nothing crashes — it just sends you three months down a wrong conclusion.

**The fix**: the yellow-tier **Read-it checkpoint** is aimed squarely at this. Every change comes with what the key lines do, **where this is most likely to be silently wrong**, and a check you can run yourself. The list is in [`references/practice-menu.md`](references/practice-menu.md).

### #2 The loss went down, but you don't know if it learned anything

**The problem**: the loss drops, the metric gains three points — is that the change working, or data leakage, or noise, or reward hacking? **Deciding "how much counts as improvement" after seeing the result will almost always produce "it improved."**

**The fix**: write the **pre-registration** (hypothesis / control / variable / **criterion** / stop-loss / prediction) before the run, and have the run-status output print the **criterion** directly above the metrics. At the moment you read the number, you're forced to check it against a standard you set in advance. See [`references/experiment-design.md`](references/experiment-design.md).

### #3 The run finished and the next step is pure vibes

**The problem**: continue or stop, which parameter to change, whether to add GPUs — nobody makes these calls for you. The AI doesn't know your business or your data either, so it can't give you a reliable answer.

**The fix**: the red tier withholds the answer and supplies scaffolding. You say what you intend to do next and why, and then we compare. The decision stays yours.

### #4 I've stopped doing the "judging" part

**The problem**: the agent writes nearly all the code and you review less and less. Judgment isn't taken from you by AI — it atrophies from disuse. And it doesn't lose value as AI gets better; it gains value as AI produces more.

**The fix**: a mastery ledger schedules reviews on a 1 / 3 / 7 / 16 / 35 day spacing, dropping a tier for topics that have stabilized and raising one for topics you keep fumbling. When you want to practice on purpose, run `/coach-drill`.

---

> One line runs through all of it: **the division of labor is not about who writes the code, it is about who is accountable for the result.**

---

## How the two skills divide the work

This repo installs two skills, split by **who can trigger them**:

| Skill | Trigger | What it does | Resident cost |
|---|---|---|---|
| `ai-coding-coach` | **Automatic** (model-invoked) | Standing discipline. Active whenever you write code, debug, or read a log, pulling you into the judgment | The description only |
| `/coach-drill` | **You type it** (user-invoked) | Explicit orchestration. Run it when you want a 15–25 minute practice session; it picks due topics from the ledger and drills them | The description only |

Only the two descriptions are resident. The substance — `SKILL.md` and the `references/` files — loads on demand, when the situation actually calls for it. So the standing cost is a couple of short descriptions, which is less than a typical `CLAUDE.md` rule or the description of one MCP server. If you want the exact number for your version, `claude plugin details` will compute it.

`coach-drill`'s description stays in the skill list on purpose: `disable-model-invocation` turns off **automatic triggering**, not the description, so you still know the door is there.

---

## How it works

### 1. Every task gets tiered first

Two questions decide how much to teach: **how quietly does this fail if it's wrong?** and **how much does doing it by hand build judgment?**

| Tier | Typical tasks | What the coach does |
|---|---|---|
| 🟢 **Green: let go** | boilerplate, argparse, logging, plotting, shell commands | Does it well, **no teaching** (no growth in it; unsolicited lessons are noise) |
| 🟡 **Yellow: read it** | data pipelines, training loops, loss implementations, eval code, hyperparameter changes | Does it, then attaches a Read-it checkpoint of 6 lines or fewer |
| 🔴 **Red: by hand** | attention / loss / sampling / optimizers, design decisions, **experiment design**, **reading a run, deciding next steps** | Coach mode: you go first, then feedback |

When unsure, it tiers yellow. Better to under-teach than to interrupt where it shouldn't.

### 2. Yellow tier: the Read-it checkpoint

Not a vague "you should understand this code" — specific:

- **Key lines**: the 1–3 lines that matter most, and why they're written that way
- **Silent risk**: the one or two ways this is most likely to be quietly wrong, plus a check you can run
- **Predict before you run**: shape / loss magnitude / output form
- **Self-check**: one situational question, no answer attached

**Silent risk** is the core of it — the most dangerous bug in this work is the one that **runs, prints a metric, and is wrong**.

### 3. Red tier: coach mode

Scaffolding first (function signature, expected output, `allclose` against an official implementation), then you write a version, then we compare.

**Teaching is an add-on, not a gate.** Want the answer? Say "just give it" and you get it immediately.

### 4. The mastery ledger (optional)

With your consent, the Pro edition's `scripts/ledger.py` records a mastery level per topic locally, schedules reviews on a 1 / 3 / 7 / 16 / 35 day spacing, and adjusts the tier accordingly: **stabilized topics drop a tier, repeatedly fumbled topics rise one.**

Where there's no local storage — a web chat, say — it prints a **study card** instead: plain text you paste into your own notes and paste back at the start of the next conversation.

> It records topic tags, outcomes, and a one-line note. No code, no hostnames, no internal addresses, no keys, no colleague names.

### 5. Intensity is adjustable

| Intensity | Trigger | Effect |
|---|---|---|
| Light | "in a hurry", "just do it" | All three tiers just get done; only the one-line silent-risk note survives |
| Standard | default | At most one red-tier invitation per session |
| Intense | "drill me", "coach mode" | Yellow upgrades to write-first-then-review; red stops offering the exit up front |

---

## Install

One command, straight into a Claude Code session:

```
/plugin install ai-coding-coach --marketplace jackeyloveseven/ai-coding-coach
```

Then use `/plugin` to check status, update, or uninstall. Open a new session afterwards — no other configuration. The skill activates on its own when you write code, change code, debug, read a training log, or design an experiment.

<details>
<summary><strong>Prefer not to use the plugin system? Clone the skill directory</strong></summary>

Personal scope (available in every project):

```bash
git clone https://github.com/jackeyloveseven/ai-coding-coach ~/.claude/skills/ai-coding-coach
```

Windows PowerShell:

```powershell
git clone https://github.com/jackeyloveseven/ai-coding-coach "$env:USERPROFILE\.claude\skills\ai-coding-coach"
```

Project scope (only inside this repository):

```bash
git clone https://github.com/jackeyloveseven/ai-coding-coach .claude/skills/ai-coding-coach
```

> This installs `ai-coding-coach` **only** — `/coach-drill` won't come along, so use the plugin if you want both. Cloning also means no automatic updates; you'll `git pull` yourself.

</details>

---

## Editions

Two editions of the same skill. The Community edition is this repository, on the `main` branch. The Pro edition is the `pro` branch, which is this one plus the tooling.

| | **Community** (`main`) | **Pro** (`pro`) |
|---|---|---|
| License | MIT | Commercial |
| Coaching discipline (`SKILL.md`, `/coach-drill`) | ✅ | ✅ |
| All six `references/` | ✅ | ✅ |
| Run-tracking tool (`exptool/`) | — | ✅ |
| Mastery ledger (`scripts/ledger.py`) | — | ✅ |
| Expanded question bank | — | ✅ |
| Updates | Community | Priority |

The Community edition is a complete, working coaching skill — not a crippled demo. Without the Pro tooling it falls back gracefully: you read the run yourself instead of using the report renderer, and you keep study cards instead of a ledger.

**Pro** is for people who want the tooling that enforces the discipline: `exptool` prints the underlying command before every action and renders a single-file self-contained HTML report of a run, and the ledger turns spaced review from a good intention into something that actually happens.

---

## Repository layout

```
ai-coding-coach/
├── .claude-plugin/
│   └── marketplace.json                  # Plugin manifest; enables one-command /plugin install
├── .github/workflows/
│   ├── test.yml                          # CI: tests on both ubuntu and windows
│   └── pages.yml                         # Publishes site/ to GitHub Pages
├── site/index.html                       # Landing page (single file, no build step)
├── SKILL.md                              # The resident skill: tiering, the three tiers, intensity and budget
├── skills/
│   └── coach-drill/SKILL.md              # /coach-drill: the explicitly triggered practice session
├── references/                           # Shared by both skills; loaded on demand
│   ├── training-run-literacy.md          # Reading logs and metrics, run status, triage
│   ├── reviewing-ai-output.md            # The five-step review, AI failure modes, change map, learning stubs
│   ├── experiment-design.md              # Pre-registration, ablation design, paper-reproduction protocol
│   ├── question-bank.md                  # Question-writing rules, types, level selection, seed questions
│   ├── mastery-ledger.md                 # Levels, spaced review, assessment, study cards
│   └── practice-menu.md                  # Write-first-then-review, the four verification habits, silent bugs
└── LICENSE-COMMERCIAL                    # Terms for the Pro edition
```

The Pro branch adds two things on top of this: `exptool/` (the run-tracking tool) and `scripts/ledger.py` (the mastery ledger). Everything else is identical.

The reference files load on demand, never all at once.

---

## The ledger script (Pro)

Ships on the `pro` branch. Without it, the skill falls back to the study card described above — same levels, same intervals, just kept by hand.

```bash
python3 scripts/ledger.py record dpo-loss pass --note "got beta's role right"
python3 scripts/ledger.py record attention-mask fail --note "mask direction backwards"
python3 scripts/ledger.py record grad-norm-reading pass --level 3   # set the level directly when evidence is strong
python3 scripts/ledger.py due --limit 3    # what's due for review
python3 scripts/ledger.py show             # every topic, with tier suggestions
python3 scripts/ledger.py card             # export a study card
```

The ledger defaults to `~/.ai-coding-coach/ledger.json`; set `COACH_LEDGER` to move it. If it reads a corrupt file it errors out and stops rather than overwriting it.

Mastery levels:

| Level | Meaning |
|---|---|
| 0 | Not yet |
| 1 | Can read |
| 2 | Can predict (gets shape, loss magnitude and output form right before running) |
| 3 | Can write unaided |
| 4 | Can find bugs, can teach others |

**Evidence has to be something you did** — answered a self-check correctly, predicted accurately, differed only trivially from the reference, found the bug in a bug hunt. Saying "I get it" doesn't count.

---

## Companion tooling: exptool (Pro)

Ships on the `pro` branch.

[`references/training-run-literacy.md`](references/training-run-literacy.md) covers how to read a training log and judge a run's status. `exptool/` is the execution entry point for that method — it collects launching, inspecting and resuming runs into a single `exp` command.

Two design principles, and only two:

1. **Every command prints the command it actually runs** (a grey `+ ssh ...`). Copy it, modify it, use it directly — once you're comfortable you don't need the tool.
2. **Read the trend, not the step.** Cut the whole run into segments and compare segment means.

It also reads a `PLAN.md` (the pre-registration) from the experiment directory and prints the **criterion** directly above the metrics. Deciding "how much counts as improvement" after seeing the result will almost always produce "it improved"; put the criterion next to the number and self-deception gets harder. With no `PLAN.md`, `exp plan <name>` generates the six-item template.

Curves are what graphs are for; reading them in a table means staring at single steps. `exp report <name>` renders one run as a **single self-contained HTML file** — zero external references, openable offline by double-click: trend curves (thin line is the raw per-step value, heavy dotted line is the segment mean), the 8-segment means table, health checks, and a reference line for the criterion. If it can recognize the metric and the value it draws the line; if not, it degrades to an annotation strip above the chart rather than drawing something wrong. And when the reference was inferred from this run's own data, the report says so explicitly — that it is not the criterion itself, and that reading still goes by what the `PLAN` says.

It is a **generic, sanitized** version — hostnames, shared-disk paths and reward-service addresses all come from a config file. On the `pro` branch it runs locally with no cluster:

```bash
cd exptool
cp runs.conf.example runs.conf
./exp list && ./exp status demo-sft
```

Details, plus the list of what is and isn't verified, are in `exptool/README.md` on the `pro` branch.

---

## Design tradeoffs

A few deliberate decisions that may look counterintuitive:

- **No teaching at green tier.** Learning API syntax or matplotlib styling adds nothing. Teaching there is noise, and noise is annoying.
- **Teaching is not a gate.** When the user clearly wants the answer, they get it. The value of a coach is getting you to move, not blocking you.
- **The checkpoint is not a mandatory footer.** If there's nothing worth saying, don't say anything.
- **One or two points at a time.** A list of ten is a list of none.
- **Calibrated confidence beats sounding expert.** Technical claims are labelled certain, rule of thumb, or not sure. Teaching something wrong is worse than not teaching.
- **The AI's own mistakes are teaching material.** When it's wrong, it says so, explains what was wrong, and turns it into a review exercise.

---

## Status and scope

This skill grew out of actual use rather than being designed up front, and it says so. What that means in practice:

- The tiering criteria are empirical. What counts as red-tier differs across CV, NLP, recommender systems and speech.
- Mastery levels rest on the coach's observation, not an objective benchmark.
- The current coverage leans toward training experiments in diffusion and RL post-training. Other areas will need adjusting.
- The question bank and the silent-bug list are seeds, not complete references.

Known limits are stated rather than hidden, because the whole skill is built on calibrated confidence — a product that oversells itself contradicts its own teaching.

Issues and PRs welcome. If you work out a better tiering or a better question for your own area, that's especially welcome.

---

## License

The Community edition is [MIT](LICENSE) — use it, modify it, build on it, ship it commercially, keep the copyright notice.

The Pro edition is covered by [LICENSE-COMMERCIAL](LICENSE-COMMERCIAL): all rights reserved, no redistribution or resale.
