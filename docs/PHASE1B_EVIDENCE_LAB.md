# Phase 1B: Evidence and Counterexample Evaluation Lab

## Research question

Can cells independently evaluate candidate experiences, reject claims contradicted by observations, retract an earlier acceptance when a counterexample arrives, and recover their evaluation state after a simulated network partition?

This lab is deliberately separate from the Phase 0 engine and the Phase 1 message-delivery lab.

## Toy benchmark

The evaluator uses the hidden reference relation `y = x mod 2` over integer inputs 0..31. Candidate rules are `parity` (correct), `constant_zero` (false), and `inverted_parity` (false). Simulated cells receive only a rule identifier and observed input/output examples; the oracle label is used only to score results. To create a meaningful adversarial case, evidence for `constant_zero` initially samples only even inputs, making the false rule appear consistent. Later, a counterexample with an odd input is sent to expose the error.

A cell accepts a hypothesis after at least three distinct observations are consistent with its rule. Any observed contradiction changes the status to rejected. If a previously accepted hypothesis is contradicted, a retraction is counted. This is a simple falsifiable baseline, not a general-purpose induction algorithm.

## Metrics

- **False-acceptance rate:** false hypotheses currently accepted / all false hypotheses seen.
- **False-rejection rate:** true hypotheses currently rejected / all true hypotheses seen.
- **Correct rejection:** number of false hypotheses rejected after evidence.
- **Retractions:** accepted hypotheses later rejected due to contradictory observations.
- **Recovery:** after a simulated partition, the returning cell reconstructs the same set of local hypotheses from replayed proposals, evidence, and counterexamples.
- **Scale sweep:** default cell counts 2, 4, 8, and 16.

## Run

```bash
python -m unittest discover -s tests -v
python -m evo_geo.evidence_lab
```

## Limits

This is a deterministic in-process simulation using a tiny finite rule family. It does not prove robust scientific reasoning, general concept discovery, cryptographic provenance, Byzantine fault tolerance, real-network recovery, or AGI. Evidence is supplied as labeled observations; the model does not independently perceive the world or discover its own representation. A larger follow-up should use hidden rule families, held-out domains, adversarial evidence, calibrated confidence, provenance/signatures, and explicit false-accept/false-reject confidence intervals.
