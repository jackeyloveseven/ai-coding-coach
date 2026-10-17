# Pre-registration - write it before the run, check against it after

Hypothesis: dropping the learning rate from 2e-5 to 1e-5 will make the SFT validation loss steadier, because the tail is noisy right now
Control: the baseline is the lr=2e-5 run, same data, same step count, same evaluation - only the learning rate differs
Variable: only the learning rate changes in this run
Criterion: judge by eval loss on the fixed dev set; it must come in at least 0.02 lower than the baseline
Budget and stop-loss: run for at most 8 hours; stop early if the loss rises instead of falling over the first 200 steps
Prediction: I expect eval loss 0.01-0.03 lower, confidence medium
