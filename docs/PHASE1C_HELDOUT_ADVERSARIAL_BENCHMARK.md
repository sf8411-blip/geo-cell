# Phase 1C — held-out and adversarial evidence benchmark

## Purpose

This experiment addresses three weaknesses of the Phase 1B toy test: a single target relation, no explicit held-out evaluation, and no estimate of statistical uncertainty. It evaluates a **finite-grammar induction baseline** under reproducible synthetic trials.

## Protocol

- Domain: integers 0–63 with binary labels.
- Candidate grammar: parity, bit-count parity, modular residue indicators, thresholds, and periodic block rules.
- Per trial, the evaluator chooses a hidden target from five target functions. Some targets (prime indicator and two compositions of simpler predicates) are intentionally outside the learner's candidate grammar.
- Two split regimes are evaluated: random 16/48 train/held-out points, and a range-shift regime training on the low-valued prefix and testing on the remaining high-valued range.
- The learner selects the candidate with the lowest error on observed training labels; ties are broken deterministically by rule name and reported.
- Adversarial conditions flip a specified fraction (0%, 10%, or 25%) of training labels. Held-out error is computed against clean target labels.
- Two baselines receive the same training/test split: a majority-label predictor and a seeded random candidate-rule predictor.
- The benchmark repeats trials across seeds and reports false acceptance, held-out failure, exact-rule-match, ambiguity, baseline errors, paired error deltas, and win rates.
- False-acceptance and held-out-failure proportions include 95% Wilson score intervals. Mean paired error differences are descriptive only and do not yet have confidence intervals.

## Run

```bash
python -m evo_geo.heldout_benchmark
python -m unittest discover -s tests -v
```

The JSON output is deterministic for a fixed seed, configuration, Python semantics, and implementation version.

## Interpretation

A **false acceptance** here means the selected candidate fits every observed training label but disagrees with the target on at least one held-out input. This is an operational benchmark metric, not a universal definition of false belief. An adversarial flip is a synthetic corruption model, not a full Byzantine network attack.

The evaluator's target family is finite and explicitly encoded, while its identity is hidden during selection. The learner's candidate grammar is known but cannot represent every target. Therefore this experiment tests generalization under model misspecification within a small DSL; it does **not** establish open-ended rule invention, self-modification of representations, calibrated confidence, cryptographic provenance, real-device decentralization, scientific discovery, or AGI.

A Wilson interval quantifies binomial sampling uncertainty under the trial model; it does not account for model misspecification or make synthetic trials representative of real environments. The range-shift split is deliberately harsher than random sampling and is not interchangeable with IID generalization. Results must be reported with the seed, trial count, split mode, split size, attack rate, and candidate grammar.

## Next falsification gates

1. Sweep training-set size and target-family complexity.
2. Add targeted and colluding multi-proposer attacks with evidence provenance and conflict preservation.
3. Add repeated-run uncertainty intervals for paired baseline differences and correct for multiple comparisons when testing many conditions.
4. Pre-register acceptance criteria and report every failed seed.
5. Add mutation/property-based testing and test the experiment against known counterexamples.
6. Keep all claims bounded to the tested grammar and protocol.
