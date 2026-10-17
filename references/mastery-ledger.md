# The mastery ledger

This is what lets tiering adapt as the user grows, and what gives review a basis. Without it, red-tier stays red-tier forever, the user never finds out they've learned something, and nothing they learned gets revisited.

Contents: 1 Two ways to store it · 2 Consent and privacy · 3 Levels and evidence · 4 How it moves the tier · 5 Spaced review · 6 The assessment · 7 Study-card format · 8 Script usage · 9 Superseding old understanding

## 1 Two ways to store it

**A. There is a persistent local filesystem** (Claude Code, a local workspace) and the user agrees: use `scripts/ledger.py`. The ledger lives locally and survives across sessions.

**B. There is no persistent storage** (a web chat where the container resets and the skill directory is read-only): do not pretend to remember. Print a **study card** at wrap-up (format in §7), ask the user to save it in their own notes, and have them paste it back at the start of the next conversation. You read it and behave as the ledger.

**Which one you're in** depends on where you're running. On the user's own machine (Claude Code, a local workspace) it's A. In a sandbox that resets (web chat, files delivered through an upload step, read-only skill directory) it's B. Don't decide by "can I write a file" — writing succeeds in a sandbox too, and then the session ends and it's gone. If you're unsure, use B, because B never writes anything.

## 2 Consent and privacy

- **Create or write the ledger only after the user explicitly agrees.** At the end of the first substantial session, ask once — folding the assessment into the same question (§6): "Want to turn on a learning record? Then I can adjust how much I teach based on what you already have, and schedule reviews. We could also do a 10-minute assessment while we're at it." If they decline, drop it and never write a file.
- If they say "turn on the learning record" or "note that down", start. If they say "turn it off" or "stop recording", stop.
- Record **topic tags, outcomes, and a note of at most one sentence.** No code, no hostnames, no internal addresses, no keys, no colleague names, and nothing about the project that isn't about the learning.
- Topic tags are lowercase-hyphenated and mid-grained: `dpo-loss`, `attention-mask`, `data-leakage`, `grad-norm-reading`, `experiment-baseline`. Too coarse (`pytorch`) can't drive a targeted review; too fine (`line-42-bug`) has no reuse value.

## 3 Levels and evidence

| Level | Meaning | Typical evidence |
|---|---|---|
| 0 | Not yet | Wrong on a key concept, or no exposure at all |
| 1 | Can read | Can restate what this code does |
| 2 | Can predict | Gets shape, loss magnitude and output form right before running |
| 3 | Can write unaided | In write-first-then-review, differences are few and minor |
| 4 | Can find bugs, can teach | Found the silent bug in a bug hunt; can explain it clearly to someone else |

**Evidence has to be something they did**: answered a self-check correctly, predicted accurately, differed only trivially from the reference, found the bug. Their own "I get it" does not count, and **"you explained it" counts even less**. Hearing it, reading it, nodding along — that is coverage, and coverage is not learning. Explaining is not learning either: only producing it unaided raises the level. Until they produce it, the topic stays where it is, unmoved by having been explained.

Outcomes: `pass` means they got it right unaided; `partial` means partly; `fail` means a key concept was wrong. When the evidence is strong you can set the level directly with `--level` — for instance, they wrote a complete correct implementation unaided, so record 3.

## 4 How it moves the tier

The ledger produces a **suggestion**. The user's own division of labor always outranks it, and anything they explicitly reserved for themselves is unaffected.

| Level on that topic | Tier shift |
|---|---|
| 0–1 | Default tier; for a topic they keep fumbling, invite one tier higher (yellow rises to a red invitation, still within the per-session red budget) |
| 2 | Default tier |
| 3–4 | Drop one tier: red becomes yellow, yellow becomes green. **But keep the one-line silent-risk note** — that's about correctness, and it doesn't disappear with familiarity |

## 5 Spaced review

- The higher the level, the longer the interval: 1 / 3 / 7 / 16 / 35 days. An incomplete answer shortens the interval; a wrong answer brings it back tomorrow.
- **Review goes with the flow; it never interrupts.** Ask only when the current task touches a due topic — they're writing DPO code and `dpo-loss` happens to be due, so slip one question in. Don't force review into an unrelated task.
- At most one or two review questions per session.
- If a ledger exists, running `due` at the start of a session to see what's waiting is fine. Keep it in mind and use it at the right moment — don't open with a quiz.

## 6 The assessment

One-off, and voluntary. Its purpose is to tell you where to start teaching.

**How to offer it**: fold it into the same question as the learning-record invitation in §2 — don't ask twice. Wanting the record without the assessment is fine. The assessment is 6–8 short questions, after which you know where to teach more and where to say less.

**Content**: one or two questions per area, drawn from `question-bank.md`, covering:

1. PyTorch and training-loop fundamentals
2. Losses and training objectives
3. Data and evaluation
4. The methods in their own area (SFT / DPO / RL / diffusion)
5. Experiment design
6. Triage and reading a run

**Flow**: one question at a time; no answers given, respond after each; record one level per area.

**At the end**, three lines: strengths, areas to shore up, and a suggested first exercise. Matter-of-fact tone. No judgement.

## 7 Study-card format

With no persistent storage, print this at wrap-up:

```
# Study card (<date>)
| Topic | Level | Last | Next review |
|---|---|---|---|
| dpo-loss | 2 can predict | 2026-09-29 | 2026-10-06 |
| attention-mask | 0 not yet | 2026-09-29 | 2026-09-30 |

Recurring mistakes:
- attention-mask: wrote the mask direction backwards
```

When they paste it back next time, read it, and print an updated card at the end of that session.

## 8 Script usage

```bash
python3 scripts/ledger.py record dpo-loss pass --note "got beta's role right"
python3 scripts/ledger.py record attention-mask fail --note "mask direction backwards"
python3 scripts/ledger.py record grad-norm-reading pass --level 3   # set the level directly when evidence is strong
python3 scripts/ledger.py due --limit 3    # what's due for review
python3 scripts/ledger.py show             # every topic, with tier suggestions
python3 scripts/ledger.py card             # export a study card
```

The ledger defaults to `~/.ai-coding-coach/ledger.json`; set `COACH_LEDGER` to move it. If the script reads a corrupt file it errors out and stops rather than overwriting it.

## 9 Superseding old understanding

Understanding deepens, and it also gets corrected. When that happens, **mark the old entry superseded — don't delete it.**

- "How the understanding changed" is itself a useful signal: which wrong path they came from tells you where they might trip next.
- An old misunderstanding is rarely isolated. It often predicts a related topic that will trip them again. Delete it and that thread is gone.
- Concretely: keep the old entry (the ledger history already retains the most recent few anyway), and write in the new note what the old understanding was and what replaced it. The study card can keep a struck-through line for the old conclusion.

This pairs with "evidence has to be something they did": a supersede only takes effect once they produce new evidence. "I get it now, that earlier thing was wrong" still doesn't count — see §3.
