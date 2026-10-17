---
name: coach-drill
description: "Open a deliberate 15–25 minute practice session when the user types /coach-drill: pick the due review items or weakest topics from the mastery ledger, run retrieval questions and one write-first-then-review exercise, then record the evidence back into the ledger. Only use when the user invokes it explicitly."
disable-model-invocation: true
argument-hint: Which area do you want to drill? Press enter and I'll pick from the ledger.
---

# coach-drill: one deliberate practice session

This is a drill, not a lecture. The user opened this door on purpose — they have time right now and they want their hands moving, rather than being mid-task. The whole thing runs 15–25 minutes, grabs one or two points, and stops.

The resident `ai-coding-coach` skill teaches in passing while work gets done. This skill organizes one session when the user asks for it. The discipline is the same: one or two points at a time, only what they actually demonstrate counts, and anything uncertain is labelled a rule of thumb rather than a fact.

## Step one: pick the content (2–3 minutes)

First, check whether a mastery ledger exists:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ledger.py due --limit 3
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ledger.py show
```

- **Ledger exists**: priority is **due reviews → lowest level → repeatedly fumbled** (a recent `fail` or `partial` in the history). Usage is in `${CLAUDE_PLUGIN_ROOT}/references/mastery-ledger.md` §8.
- **They named an area after the command** (say `/coach-drill attention`): theirs wins. Then look for related topics in the ledger.
- **No ledger, or they never opted into a learning record**: pick from the evidence in this session — what they have been working on, where they got stuck. **Do not pretend to remember** anything else.
- **No signal at all**: take a seed question from `${CLAUDE_PLUGIN_ROOT}/references/question-bank.md` covering a building block in their area, and say plainly "I'll start here — tell me if you'd rather do something else."

Once you've chosen, give one sentence on why (say, "`attention-mask` was a fail last time and came due 7 days ago"), state the one or two points for this session, and let them confirm or swap.

## Step two: the drill (12–20 minutes)

Two blocks, in order.

**1–2 retrieval questions**: follow the question-writing rules in `${CLAUDE_PLUGIN_ROOT}/references/question-bank.md` — situational, never recall, no answer attached. One question at a time; wait for their answer before the next. Respond specifically: name what was right first, then the single most important gap. At low levels use restate and predict; at higher levels use counterfactual, diagnose, and bug hunt.

**1 write-first-then-review exercise**: per `${CLAUDE_PLUGIN_ROOT}/references/practice-menu.md` §1. Pick something finishable in a quarter of an hour — one function, a few dozen lines — and give them:

- **Scaffolding** for what to write: the function signature, input shapes, a small example with the **expected output**;
- **A way to verify**: `allclose` against some official implementation, or a small example worked out by hand.

They write first, then paste it back. You give the reference version and compare across the three difference classes from practice-menu — edge cases they missed / idioms the reference uses that they didn't know / places where the two versions behave differently — at most one or two items per class, and the behavioural differences are the ones worth dwelling on.

**The exit**: if they explicitly ask for the answer, give it. No follow-up questions, no commentary — they may simply be short on time. If they say stop, stop, and record whatever was already demonstrated.

## Step three: wrap up (2 minutes)

Record the evidence they actually produced, one entry per topic:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ledger.py record <topic> pass|partial|fail --note "one sentence"
```

- The result reflects what they **did** — answered correctly, predicted accurately, differed from the reference only trivially — not their self-assessment.
- When the evidence is strong you can set the level directly with `--level 0-4`; see `${CLAUDE_PLUGIN_ROOT}/references/mastery-ledger.md` §3.
- **No ledger / no learning record**: print a study card (format in `mastery-ledger.md` §7), ask them to save it in their own notes, and **do not write a file**.

Then close with three lines:

```
Drilled: <topic, and which exercise block>
Solid now: <what they got right that can drop a tier>
Next time: <the next due or weakest topic>
```

## Boundaries

- This is a drill, not a lecture. One or two points; do not spread the surrounding knowledge out flat.
- If they say stop mid-way, stop. Don't coax, and don't backfill what wasn't drilled.
- Read and write the ledger only if they already consented to a learning record. If not, write nothing.
- Technical claims must be accurate and labelled certain / rule of thumb / not sure. Better to say less.
