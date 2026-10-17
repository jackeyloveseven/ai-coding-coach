# Question bank and how to write questions

Used for yellow-tier self-checks, quiz-me mode, and due reviews. A good question exposes a gap in understanding; a bad one tests memory.

Contents: 1 How to write questions · 2 Question types · 3 Choosing by level · 4 Responding to an answer · 5 Seed questions · 6 Fair construction for multiple choice · 7 Retrieval beats re-reading

## 1 How to write questions

- **Situational, never definitional.** "What is a mask" is a bad question. "This batch has sequences of different lengths — what should happen to the loss at the padding positions?" is a good one.
- **One question at a time.** Wait for the answer before the next.
- **No answer attached.** The answer comes after they've answered.
- **Draw on code they just worked on or a log they just read.** It sticks far better than a generic question.
- **Never test recall.** Specific default values and function names are one lookup away; they aren't worth examining.
- Technical claims must be accurate. If you're not sure of the answer, don't ask the question. Better to ask fewer.

## 2 Question types

| Type | Form | What it tests |
|---|---|---|
| Restate | Explain in your own words what this code does and why | Whether they actually read it |
| Predict | Run this — what shape, loss, output? | Whether the mental model is accurate |
| Counterfactual | If X became Y, what happens? | Whether they understand causation |
| Diagnose | Given a symptom, find the possible causes | Debugging instinct |
| Trade-off | Two metrics move in opposite directions — how do you choose? | Judgment |
| Bug hunt | Code that runs but is silently wrong — find it | Reviewing ability |

## 3 Choosing by level

Level definitions are in `mastery-ledger.md`. Without a ledger, judge from the session.

- Level 0–1: restate, predict. Confirm comprehension first.
- Level 2: counterfactual, diagnose.
- Level 3 and up: trade-off, bug hunt.

## 4 Responding to an answer

1. Name specifically what they got right.
2. Point at the single most important gap — not a list.
3. Explain the reason behind the gap. Don't just hand over the correct answer.
4. Sort the outcome into `pass` (correct unaided), `partial` (partly), `fail` (a key concept was wrong), and record it when a ledger exists. Judge by what they **produced**, not by their self-assessment.

## 5 Seed questions

"Key points" is what a good answer should contain — use it to check their answer, don't read it out to them. Items marked *(rule of thumb)* are common tendencies, not absolutes.

**PyTorch and the training loop**

| Question | Key points |
|---|---|
| What happens if you forget to zero the gradients before each `backward()`? | PyTorch accumulates gradients by default, which implicitly enlarges the batch — usually not what you meant. Gradient accumulation is the same mechanism, used deliberately |
| What do `model.eval()` and `torch.no_grad()` each control? What breaks if you only use one? | The first changes the behavior of dropout, BatchNorm and similar layers; the second turns off gradient recording to save memory. They're independent and do different jobs |
| You multiply a per-token loss of shape `(B, T)` by per-sample weights of shape `(B,)`. What happens? | Broadcasting aligns trailing dimensions; `B != T` errors, but when `B == T` it silently multiplies along the wrong axis. Use an explicit `unsqueeze(-1)` |
| Training looks fine but eval metrics are terrible. What do you check first? | Train/eval mode, whether preprocessing matches, whether the eval data is being read correctly, and the mirror image of data leakage |

**SFT**

| Question | Key points |
|---|---|
| Why do you usually mask the prompt out of the loss during SFT? | The goal is to learn to generate the response, not to recite the prompt; leaving it in spends capacity on predicting the prompt. Some setups keep it, depending on the task *(rule of thumb)* |
| How should padding positions be handled in the loss, and what happens if you miss them? | Exclude them with an ignore index or a mask; otherwise the loss is dragged around by padding, and correlated with sequence length |
| Training loss keeps falling while validation loss turns upward partway through. What does that mean? | The classic overfitting signal. Could be too little data, too many epochs, or too large a learning rate; the fix follows the cause |

**DPO**

| Question | Key points |
|---|---|
| If you raise β, does the model move closer to or further from the reference? Why? | Closer. A larger β strengthens the implicit penalty on deviation |
| Why does DPO need a reference model? | The objective compares the policy's preference *relative to the reference*; the reference supplies the baseline and constrains how far the policy can drift |
| Mid-training the margin is growing but the chosen log-probability is also falling. Is that a bug? | Not necessarily. DPO optimizes a relative difference, and falling absolute probabilities are a known phenomenon *(rule of thumb)*. Confirm with generated samples and evaluation that quality hasn't degraded |
| `rewards/accuracies` reaches 1 quickly. Is that good? | It may mean the task is easy or the model has overlearned. Look at generation quality, not just this number |

**RL post-training (general)**

| Question | Key points |
|---|---|
| Training reward climbs steadily. Why isn't that direct evidence the model improved? | The prompts differ each step, the distribution drifts, and reward hacking is possible. Use a fixed eval set, and look at samples |
| How do you detect reward hacking? | Compare samples from different checkpoints side by side on fixed prompts; cross-check with an independent metric; look at it with your own eyes |
| What happens if the KL penalty coefficient is too large, or too small? | Too small and the policy drifts or exploits reward loopholes; too large and it barely learns *(rule of thumb)* |

**Diffusion and flow**

| Question | Key points |
|---|---|
| Given x0, how do you construct a noisy sample for training? What's the difference between predicting noise, x0, and v? | The forward process has a closed form, so you can sample directly from x0 to any timestep in one step. The three are different parameterizations of the same objective, differing in numerical scale and training stability |
| What usually happens when you turn up the classifier-free guidance strength? | Prompt adherence rises and diversity falls; too high and you get oversaturation or artifacts *(rule of thumb)* |
| You halve the number of sampling steps. What happens to quality and speed? | Speed improves roughly linearly; quality depends on the sampler and the model, and has to be measured — samplers differ a lot |

**Evaluation and data**

| Question | Key points |
|---|---|
| What are the common sources of data leakage? | Train/eval overlap; preprocessing (normalization, tokenization, filtering) computing statistics over the full dataset; near-duplicate examples; selecting hyperparameters or checkpoints on the eval set |
| Metric A went up and metric B went down. How do you decide? | What each one measures; which is closer to the real goal; how large the noise is; look at samples. Don't stare at a single number |
| How do you know your eval set is large enough and stable enough? | The spread across seeds at the same configuration; the number of eval examples; an intuition for the confidence interval |

**Experiment decisions**

| Question | Key points |
|---|---|
| A new method shows no improvement. Do you suspect a bug or the idea first, and how do you tell them apart? | Rule out the bug first: overfit a tiny sample, check that gradients reach the new module, check the config took effect. Only then discuss whether the idea is inert |
| Do you plan to continue, stop, or change a parameter — and on what basis? | Whether there was a pre-registered criterion; the shape of the curve; the budget. The decision is theirs; you only fill gaps |

## 6 Fair construction for multiple choice

This section is only about making a question *fair*. An unfair question tells you nothing even when it's answered correctly.

- **Equal-length options.** Keep all options about the same length — ideally the same character count. The moment the correct option is longer and more specific, it becomes the only "detailed option" and can be picked without thinking. This one is borrowed from the `teach` skill in `mattpocock/skills` (MIT).
- **Shuffle the position of the correct answer.** Don't always put it first or last. A fixed position teaches them to guess by position rather than judge by content.
- **Don't leak the answer through formatting, ordering, or tone.** Bolding, word order, and how certain the phrasing sounds must not hint at the answer. If the correct option says "usually" and the distractors say "always" or "never", the answer is written on its face.

After writing a multiple-choice question, scan it once yourself: from the shape of the options alone — length, position, tone — can you guess the answer? If you can, rewrite it.

## 7 Retrieval beats re-reading

Having them recall from memory (retrieval practice) is far more useful than having them re-read the material.

- Re-reading produces an illusion of understanding: it reads smoothly, so it feels remembered. What it actually produces is familiarity.
- Failing to recall is the real gap, and the most valuable signal you can get.
- So "quiz me" is not a formality. It is the primary form of practice; re-reading and reviewing notes are its supplement.

"Let me read it once before answering" is fine — but then they close the material and answer from memory. Don't let them copy from the page.
