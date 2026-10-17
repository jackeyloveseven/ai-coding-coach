# Practice menu

The concrete teaching moves and the wording for them. Read this when the user asks to practice, to be quizzed, or to reproduce something, or when you need a template. Reviewing AI output is in `reviewing-ai-output.md`; experiment design in `experiment-design.md`; question writing in `question-bank.md`.

Contents: 1 Write first, then review · 2 Predict before you run · 3 The four verification habits · 4 The silent-bug list · 5 Quiz-me mode · 6 The monthly no-AI reproduction · 7 Reading good code · 8 The debrief card · 9 What is safe to skip · 10 Interleaving

## 1 Write first, then review

Flow: the user writes a version (however rough — pseudocode counts) → you write or show the reference → compare.

Compare across three classes of difference only, at most one or two items each:

- Edge cases they missed (empty input, sequence length 1, padding, a batch where every label is identical)
- Idioms or library functions the reference uses that they didn't know
- Places where the two versions **behave differently** — the most valuable class. Who's right, and why?

This beats reading your output directly, because they read with their own version in hand, and every difference has a "here's what I was thinking" anchor attached to it.

## 2 Predict before you run

Before running, have them write down:

- The shape of the key tensors
- The rough magnitude of the loss (for a classification task, the initial loss should be near `ln(number of classes)`)
- What the output should look like

Then compare after the run. A wrong prediction is a comprehension gap — stop and close it. That is a better use of the next ten minutes than writing more code.

## 3 The four verification habits

This is the most underrated skill on the list. People who are good at it get far more out of AI output than people who aren't.

1. **Overfit a tiny sample**: take 10 examples and see whether you can drive the loss to near zero. If you can't, there is a bug in the model, the loss, or the data pipeline. Do not scale up first.
2. **Unit-test the critical functions**, especially data processing and metric computation.
3. **Work a small example by hand** and compare against the code's output. DPO, attention and metric math all suit this.
4. **Fix the seed and check the split for leakage** — do train and eval overlap, and did any preprocessing step (normalization, tokenization, filtering) compute its statistics over the full dataset before the split?

## 4 The silent-bug list

Pick the yellow-tier **silent risk** from here, and only the ones that actually apply to the code in front of you:

- **Data leakage**: eval examples appearing in train; normalization statistics computed over the full dataset
- **Mask misalignment**: padding contributing to the loss; the causal mask flipped; the prompt left unmasked
- **Shape broadcasting**: two tensors of different shapes that "ran fine" because the result was silently broadcast
- **Inconsistent measurement**: different preprocessing at train and eval time; metrics compared across different data subsets
- **Train/eval mode not switched**: dropout or BatchNorm still active during evaluation
- **Gradients silently detached**: `detach` or `no_grad` in the wrong place; a reference model that was never frozen
- **LR scheduler stepped at the wrong moment**
- **Overflow or underflow under mixed precision**

## 5 Quiz-me mode

Trigger: the user says "quiz me", "give me questions", "check whether I actually understand this".

- Ask 3–5 questions drawn from code they just worked on, never recall questions. Question types, level selection and seed questions are in `question-bank.md`.
- A good type is **bug hunt**: hand them under 20 lines with one silent bug — it runs, but the result is wrong — and have them find it.
- Another is **restate**: have them explain in their own words what the code does and why it's written that way; you point out where the explanation went wrong.
- One question at a time. Wait for the answer before the next.

## 6 The monthly no-AI reproduction

Trigger: the user asks "what should I practice" or wants to reproduce something.

Once a month, pick a classic model or a paper and **reproduce it from scratch without AI** — data, model, training, evaluation, all four. It will hurt. It is also the densest form of understanding there is. Some people hold themselves to a ratio: 20–30% of their time without AI.

Your role here is **reviewer, not ghostwriter**. When they finish, help them find the problems. When they're stuck, give direction along the hint ladder, nothing more. For paper reproduction, follow the protocol in `experiment-design.md` §5.

Pick something in their own area, sized to "one or two weekends". Examples: a minimal DPO training loop; SFT with masking; training and sampling a small diffusion model; writing a progress reader for an existing training script.

## 7 Reading good code

In the AI era, reading code matters more than writing it, because most of the time is spent reviewing.

When the user wants to get better at reading:

- Help them pick what to read — one function in an open-source library, one forward pass's call chain — rather than chewing through a whole repository from the top.
- Read with a question in hand: "Why is there a `detach` here?" "How is this batch dimension being handled?"
- Reading a senior teammate's code counts too: watch how they organize things and how they handle edge cases.

## 8 The debrief card

After a substantial task, you can invite them to fill in three lines — only when they're willing; never let it become a chore. If a learning record is on, these three lines can become the ledger note; see `mastery-ledger.md`:

```
Learned today:
Still fuzzy:
Will try myself next time:
```

## 9 What is safe to skip

- Memorizing API syntax and command-line flags
- Spending a lot of time on matplotlib styling or shell scripts
- Pure recall drilling (unless they're preparing for interviews)
- Chasing every new framework and tool. Tools turn over fast; principles are worth more than tools

When they get anxious about any of these, tell them plainly that it's fine to skip, and to spend the energy on red-tier material instead.

## 10 Interleaving

**Interleaving** means mixing related but distinct topics in one sitting, rather than grinding a single topic to the end.

- For example, alternate `attention-mask`, `dpo-loss` and `data-leakage` within one session, instead of mask today and loss tomorrow.
- It forces the classification step — "what kind of problem is this?" — before any method gets applied. Grinding one topic to the end skips that step, so all you practice is mechanical repetition.
- In real debugging, the very first move is exactly that classification: the loss won't go down — is it the data, the objective, or the optimizer? Interleaving practices that move.

**How it divides work with spacing**: two different jobs.

| | What it governs | Where |
|---|---|---|
| Spacing | *When* to practice: spreading a topic's reviews over 1 / 3 / 7 / 16 / 35 days | `mastery-ledger.md` §5 |
| Interleaving | *What combination* to practice: mixing related but distinct topics | This section |

They stack. If several topics come due in one session, don't spread them across separate days — mix them and alternate.
