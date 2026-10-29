# Phase 1C — held-out and adversarial evidence benchmark

## Purpose

This experiment addresses three weaknesses of the Phase 1B toy test: a single target relation, no explicit held-out evaluation, and no estimate of statistical uncertainty. It evaluates a **finite-grammar induction baseline** under reproducible synthetic trials.

## Protocol

- Domain: integers 0–63 with binary labels.
- Candidate grammar: parity, bit-count parity, modular residue indicators, thresholds, and periodic block rules.
- Per trial, the evaluator chooses a target candidate and hides its identity from the selection procedure.
- A seeded random split assigns 16 inputs to training and the remaining 48 to held-out evaluation.
- The learner selects the candidate with the lowest error on observed training labels; ties are broken deterministically by rule name and reported.
- Adversarial conditions flip a specified fraction (0%, 10%, or 25%) of training labels. Held-out error is computed against the clean target labels.
- The benchmark repeats trials across seeds and reports false acceptance, held-out failure, exact-rule-match, ambiguity, and mean error.
- False-acceptance and held-out-failure proportions include 95% Wilson score intervals.

## Run

```bash
python -m evo_geo.heldout_benchmark
python -m unittest discover -s tests -v
```

The JSON output is deterministic for a fixed seed, configuration, Python semantics, and implementation version.

## Interpretation

A **false acceptance** here means the selected candidate fits every observed training label but disagrees with the target on at least one held-out input. This is an operational benchmark metric, not a universal definition of false belief. An adversarial flip is a synthetic corruption model, not a full Byzantine network attack.

The rule family is finite and explicitly encoded. The target identity is hidden during selection, but the candidate grammar is known. Therefore this experiment tests generalization and robustness within a small DSL; it does **not** establish open-ended rule invention, self-modification of representations, calibrated confidence, cryptographic provenance, real-device decentralization, scientific discovery, or AGI.

A Wilson interval quantifies binomial sampling uncertainty under the trial model; it does not account for model misspecification or make synthetic trials representative of real environments. Results must be reported with the seed, trial count, split size, attack rate, and candidate grammar.

## Next falsification gates

1. Compare with a majority-label baseline and a random candidate baseline under identical data.
2. Sweep training-set size and target-family complexity.
3. Include distribution shifts, not only random held-out points from the same domain.
4. Add multi-proposer attacks with provenance and conflict preservation.
5. Pre-register acceptance criteria and report every failed seed.
6. Keep all claims bounded to the tested grammar and protocol.
