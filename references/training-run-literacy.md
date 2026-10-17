# Reading a training run, and triage judgment

Contents: 1 Principles for reading · 2 What to watch per method · 3 Health checks and triage · 4 Starting a new run · 5 Self-check questions for reading a run · 6 Adapting this to your setup

Sections 1–5 are general judgment and hold over time. Section 6 is a checklist rather than a set of facts, because anything environment-specific goes stale.

## 1 Principles for reading

1. **Read the trend, not the step.** Cut the run into segments (8 is a workable number), compare segment means, and look at the direction left to right. Single-step values jump around and carry no information. A run-report tool can plot the segment means as a curve and draw the pre-registered criterion as a reference line, so you read against it directly.
2. **For RL-style methods, judge the gain on a fixed eval set.** Training reward changes prompts every step and swings wildly — don't stare at it. Only a score on a fixed eval set that sits *reliably above the starting point* means the model actually improved.
3. **Register and inspect at the level of the individual run directory.** If one SFT experiment has `smoke/` and `formal/` under it, write to `formal/`, or the records from the two runs will be mixed together.
4. **Finished is not the same as effective, and reachable is not the same as ready.** A process exiting cleanly, or an endpoint answering, only means nothing crashed. Whether it worked needs an independent evaluation; whether a service is usable needs readiness evidence.
5. **For generative tasks, the human eye is the final standard.** Metrics are a support; in the end you look at the samples.

## 2 What to watch per method

| Method | Main signal | What good looks like | What to watch for |
|---|---|---|---|
| SFT | `loss` | Falls fast, then flattens out | Training loss keeps falling while validation loss turns upward → overfitting (memorization) |
| DPO | `rewards/accuracies`, `rewards/margins` | Accuracy climbs up from 0.5, margins widen | Loss approaching 0 fast and accuracy near 1 → the task may be too easy, or the model has overlearned. Look at generation quality |
| RL post-training (reward-based) | Reward on a fixed eval set | Sits reliably above the starting point | Training reward swinging is expected — don't watch it. Some RL objectives have a loss that sits near zero by construction and is not informative |
| All methods | `grad_norm` | Roughly flat | A sudden 10× jump, or NaN/inf → a numerical problem |

## 3 Health checks and triage

Health checks first: is the session still alive; is there a failure marker file; how long ago did the log last update (a long gap can mean it's stuck on a reward service, on NCCL, or in a deadlock); did it finish with a normal status.

Problems split into two kinds, handled differently.

**Operational failures (the user should own these — basic competence)**

- An error containing `timeout`, `Connection`, `HTTP 5xx`, `reward` and the like → a network or service problem, probably temporary. Test whether the service is alive first: an HTTP `200` or `401` both mean it's up (`401` just means no credentials were sent); hanging, or a `000`, means it's down. Once the service is fine, clear the failure marker and resume.
- `CUDA out of memory` → often means someone else took the GPU. Find whose process it is (`nvidia-smi`, then `ps -o user,pid,etime,cmd -p <pid>`) before touching any code.

**Real code bugs (worth asking AI about)**

- Python tracebacks, shape mismatches, NaN. Hand the AI the full traceback and the relevant code. The teaching point: narrate the localization as a method, and after the fix have the user restate the root cause in one sentence.

## 4 Starting a new run

1. Copy an experiment directory that already works, and change only the parameters. Put the launch command in a script, and write logs to a log directory.
2. Register the run: name, machine, the exact run directory, method, session name, notes.
3. Confirm the GPUs you intend to use are free.
4. Look at GPU state once more before launching, and confirm.
5. Check the log after a minute or two to confirm the model loaded properly.
6. **Set the step count to 2 and get it running end to end first, then change it to the real number.** Find the errors at the lowest possible cost.

## 5 Self-check questions for reading a run

Pick one or two when teaching; don't attach answers:

- How much did this curve move from start to finish? Did it learn anything?
- Training loss falling while validation loss rises — what does that tell you?
- DPO loss approaching 0 fast with accuracy near 1 — is that good? What would you look at to confirm?
- `grad_norm` suddenly jumped 10×. What do you suspect first?
- Training reward went up on this RL run. How do you confirm it's real improvement and not drift from changing prompts?
- Do you plan to continue, stop, or change a parameter? On what basis?
- In this launch script, what are the learning rate, the prompts per step, and the total step count?

## 6 Adapting this to your setup

Everything below is a question to answer about *your* environment before relying on it. None of it is a fact about the world, and none of it can be assumed to still be true from one month to the next.

- **The run-tracking tool**: is there a single entry point for registering, inspecting, starting, stopping and resuming runs? If it exists, learn what it prints before it acts — a tool that echoes the underlying command before running it teaches you the command.
- **The progress reader**: how does it locate metrics? A common design is to look for a per-method script first and fall back to a generic reader, which tries a set of sources in order (`*.jsonl`, then a trainer-state file, then tensorboard event files, then patterns like `loss=0.12` in the log) and uses the first one it finds. Verify the order against your own layout, or you'll read a stale source.
- **Shared storage**: does every machine see the same files, or does the machine column determine where to look? This changes whether "check the log" and "check the GPU" are the same operation.
- **Reward thresholds**: any specific threshold for declaring an improvement belongs to one reward model and one configuration. Changing either invalidates it. Never carry a threshold across setups.
- **Reward-service health checks**: the approach is in §3. The address, port, and whether credentials are needed are all things to check as they are now — never copy an old address.
