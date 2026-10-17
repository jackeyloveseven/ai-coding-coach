# Experiment design and paper reproduction

Experiment design is the most valuable thing an ML engineer does, and AI can't take it over, because AI doesn't know the user's business or their data. This file turns "let me try this and see" into "an experiment with a hypothesis and a criterion".

Contents: 1 Pre-registration · 2 The usual traps · 3 Designing an ablation · 4 Deciding after the run · 5 The paper-reproduction protocol · 6 What to say

Most of the judgments in here are rules of thumb, not theorems. Keep that framing when you teach them.

## 1 Pre-registration

Before the run, have them write these six items down. This is "predict before you run" at the scale of an experiment — compare afterwards, and a wrong prediction is a learning point:

```
Hypothesis: I think <the change> will improve <the metric>, because <the reason>
Control: the baseline is <what>, at the same budget, same data, same evaluation
Variable: this run changes only <one thing>
Criterion: judge by <metric>; it counts as an improvement only if it moves past <how much> (decide now, not after seeing the result)
Budget and stop-loss: run for at most <how long>; stop early if <what happens>
Prediction: I expect <what>, confidence <high/medium/low>
```

The **criterion** is the item most often skipped. Deciding "how much counts as an improvement" after the results are in will almost always produce "it improved".

If you're using a run-tracking tool that supports it, let the tool hold the criterion rather than their memory: the Pro edition's `exptool` generates this template with `exp plan <run>` and prints the criterion directly above the metrics with `exp status`, so there's nothing to remember to check back against. Without a tool, the criterion goes at the top of the run's notes, and reading the metrics means scrolling past it.

## 2 The usual traps

- **Changing several variables at once**: if it works you don't know what to thank, and if it breaks you don't know what to blame.
- **An untuned baseline**: comparing a tuned new method against a stale old one.
- **Concluding from a single seed**: you don't know how large the noise is, so the difference might be nothing. Measure the same-configuration spread across seeds once, and only then do you know what difference is worth believing.
- **Selecting hyperparameters or checkpoints on the eval set**: the result comes out optimistic. The eval set is for looking at once, at the end.
- **The metric improved but the samples got worse**: watch especially for reward hacking in reward-based objectives. Any generative task needs a human looking at samples; the metric is only a support.
- **No sanity check**: going straight to a large run without having verified that a tiny sample can overfit, what the random baseline is, and roughly where the ceiling sits.
- **Reporting only the wins**: a failed experiment carries information too. One line on why it failed is worth recording.

## 3 Designing an ablation

- Each ablation corresponds to one hypothesis: "if I remove X, the metric should drop, because X is responsible for Y".
- Remove or replace one component at a time; hold everything else fixed.
- When the ablation contradicts the expectation, don't rush to explain it. First ask whether the implementation has a bug, or whether that component simply doesn't matter under this configuration.

## 4 Deciding after the run

What follows is an order of thinking, not a formula. Walk them through it themselves; you only fill the gaps they leave:

1. **Better than expected**: is it stable? Does it hold across seeds and across eval sets? Look at the generated samples — any sign of reward hacking?
2. **No change**: rule out a bug before concluding the idea is inert. Distinguish the two by overfitting a tiny sample, checking whether gradients actually reach the newly added module, and checking whether the config actually took effect.
3. **Worse**: look at the training curve and `grad_norm` for anomalies, look at the samples, identify *how* it got worse, and only then guess why.
4. Whichever it is, ask them first: "what do you plan to do next, and why?" Their call comes before your advice. The decision is theirs.

## 5 The paper-reproduction protocol

Reproduction is the densest form of understanding there is. Your role is reviewer, not ghostwriter.

1. **Read it through first and pull out four things**: the problem being solved, the core idea of the method, the experimental setup, and the key numbers in the paper.
2. **A symbol table**: have them list every key formula's symbols and map each to a variable or function in the code. The ones that don't map are the ones they haven't understood.
3. **Write it themselves first, then diff against the official implementation** if one exists. Sort every difference into three classes: bug, trick (something the implementation does that the paper doesn't mention), hyperparameter difference. Understand why each one exists.
4. **Set tiered goals**: reproduce the trend first (right direction, right order of magnitude), then chase the numbers. When the numbers don't match, check the evaluation setup, the data processing and the seeds before suspecting the method itself.
5. **Record the details the paper leaves out**. Those are often the ones that matter.

## 6 What to say

**When they say "I want to try X"**:

> Write down these six first: hypothesis, control, variable, criterion, budget and stop-loss, prediction. Paste it here and I'll pick out only the two most important holes.

**When they hand in a pre-registration**: name the specific parts that are well done first, then pick the one or two most important holes — the most common are a criterion that was never quantified, and a control that isn't fair. Don't nitpick every line.

**When they want to change several things at once**:

> If these all go in together and it works, you won't know which one to thank. Want to pick the one you most want to verify first?

**After the run**: have them compare against their own prediction first — where it matched, where it didn't — and only then does your analysis come.
