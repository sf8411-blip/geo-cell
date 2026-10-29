# Phase 1E — Adversarial multi-cell provenance scenarios

## Objective

Exercise the Phase 1D evidence model against coordinated reports, reporter-ID
multiplicity (a Sybil-like pattern), shared sources, and shared parent lineage.
This phase adds heuristic risk flags; it does not claim to solve Byzantine
consensus, authenticate identities, or prove that two sources are independent.

## Scenarios covered

1. **Coordinated reports:** multiple reporter IDs repeat a claim from one source
   and declared lineage. The audit flags source concentration and shared lineage.
2. **Reporter-ID multiplicity:** many reporter IDs claim distinct independence
   groups while citing one source. The audit reports the mismatch; it cannot prove
   the IDs are fake or the groups dishonest.
3. **Shared parent lineage:** reports cite a common parent report. The audit flags
   this correlation signal even when the immediate source IDs differ.
4. **Conflicting reports:** conflicting values remain visible; the audit does not
   choose a majority winner.
5. **Claim isolation:** reports for other claims do not inflate the selected audit.
6. **Empty evidence:** returns zero counts and no flags.

## Interpretation rules

- A flag is a review trigger, not a finding of malicious behavior.
- Distinct reporter IDs are not authenticated identities.
- Distinct source IDs and declared groups are not proof of independent evidence.
- A lack of flags is not proof of safety; colluding actors can fabricate metadata.
- The implementation does not use majority vote to resolve disagreement.
- No experience transfer or operator discovery is connected in this phase.

## Reproducibility

Run:

```bash
python -m unittest tests.test_evidence_attacks -v
python -m unittest discover -s tests -v
```

Passing tests show that these specified synthetic metadata patterns produce the
expected flags. They do not measure real-world attack detection rates or prove
network security.

## Acceptance gate

Before proceeding to operator discovery, require CI to pass on the exact commit,
review the test outputs, and preserve these limitations in the project docs.
Next research questions include authenticated cell identity, signed source
attestations, independently reproducible experiments, and false-positive /
false-negative measurement on held-out adversarial scenarios.
