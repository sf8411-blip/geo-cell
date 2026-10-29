# Phase 1F — Evidence-Guided Operator Discovery: Design Proposal

## Status and scope

**Design proposal only.** This document specifies a staged, falsifiable research program. It does not claim that the repository can currently invent arbitrary operators, revise its own computational language, or exhibit AGI. No operator-discovery engine is implemented by this document.

The Phase 1E CI gate passed on commit `f07706fe801a3339b4b65df78999fab2592643d9`; see [the validation record](PHASE1E_CI_VALIDATION_RECORD.md). Phase 1E remains a draft, unmerged PR.

## 1. Research question

Given finite observations from an unknown environment, can a system propose a candidate computational operator not present as a named rule in its initial candidate list, produce a reproducible executable definition for it, and demonstrate that the operator predicts held-out observations better than credible baselines under a fixed compute budget?

A second, strictly later question is whether the system can identify a limitation in its current representation and propose a controlled extension to its operator grammar. Passing the first question does not imply passing the second.

## 2. Non-goals and scientific constraints

- No claim of AGI, consciousness, general understanding, or unrestricted self-modification.
- No neural networks, transformers, gradient optimization, or learned human-language interface as the discovery mechanism.
- No use of evaluator-only labels, held-out examples, or oracle target definitions during candidate generation or selection.
- No majority vote as a substitute for evidence quality.
- No acceptance based only on training fit, complexity reduction on the training set, or agreement among correlated reporters.
- Every run must be seeded, replayable, budgeted, and able to return **no supported operator**.
- Operator provenance, training evidence, counterexamples, test results, and version history must be retained. A new proposal must not overwrite a prior rejected candidate.

## 3. Proposed architecture

Keep the first prototype deliberately bounded and separate its responsibilities.

1. **Observation contract:** validates input/output records, environment identity, data split, and provenance metadata. It must not expose held-out labels to the proposer.
2. **Candidate generator:** constructs small executable expressions from a versioned, explicit primitive set. Candidate generation is deterministic for a given seed and budget.
3. **Evaluator:** runs candidates only on training observations, records errors and counterexamples, and rejects malformed, non-terminating, or resource-exceeding candidates.
4. **Complexity estimator:** records a transparent description-length or syntax-cost measure. The first version uses a fixed, documented cost model rather than claiming a universal measure of simplicity.
5. **Selection and abstention policy:** returns a candidate only when it clears predeclared evidence thresholds and beats baselines; otherwise returns `insufficient_evidence`.
6. **Held-out evaluator:** runs after the candidate is frozen. Its labels are accessible to the benchmark scorer only, not to the generator or selection policy.
7. **Evidence ledger:** stores the candidate definition/hash, parent candidates, seed, budget, observed examples, counterexamples, decision, and test outcomes. Phase 1D/1E provenance flags are risk signals only, not cryptographic proof.
8. **Rollback/version manager:** rejected or later-falsified candidates remain recorded; updates are reversible and do not silently replace the current accepted operator set.

## 4. Candidate representation for the first prototype

Start with a small typed expression language over bounded integer and Boolean observations. The exact primitive list must be frozen in the implementation issue before results are inspected. A reasonable initial grammar is:

- input variables and a small set of constants;
- bounded integer addition, subtraction, and multiplication;
- equality and order comparisons;
- Boolean NOT, AND, and OR;
- bounded modular-residue tests;
- conditional selection;
- composition of already-defined expressions.

Use explicit type, range, depth, runtime, and memory limits. Division, unbounded recursion, arbitrary code execution, network access, and filesystem access are excluded from the first prototype.

A candidate's **operator novelty** is syntactic and version-relative at first: it must be a new canonical expression absent from the initial named candidate list. This is not a claim that it is mathematically or scientifically novel. Later research may define behavioral equivalence classes, but that requires its own test protocol.

## 5. Search strategy

The first implementation should use bounded enumerative synthesis or a similarly auditable search procedure, not an opaque optimizer:

1. Enumerate candidates in increasing syntax cost, with canonicalization to reduce duplicate expressions.
2. Evaluate all candidates against the same training evidence and compute budget.
3. Keep a Pareto frontier over training error, complexity, and execution cost rather than hiding trade-offs in one arbitrary score.
4. Generate counterexample queries where candidate predictions disagree, when the environment can be queried safely.
5. Re-evaluate survivors after each newly acquired observation.
6. Freeze a candidate before held-out evaluation.
7. If no candidate passes the acceptance policy, abstain.

A later comparison may test stochastic evolutionary search, but it must use the same wall-clock or evaluation budget and include multiple seeds. Search algorithms are experimental alternatives, not assumptions about the best route to intelligence.

## 6. Objective and decision policy

For a candidate program (p), report at minimum:

- empirical training error (E_{train}(p));
- held-out error (E_{heldout}(p)), available only to the scorer;
- syntax cost (L(p));
- execution cost (C(p));
- counterexample count and the conditions that generated them;
- performance against each baseline under the same budget.

A transparent training-time ranking may use a declared tuple such as
`(training_error, syntax_cost, execution_cost, canonical_program_text)`
for deterministic tie-breaking. This avoids implying that a hand-picked scalar objective is universally correct. Held-out error must never influence candidate selection.

The acceptance decision should require all of the following:
- minimum number of distinct, valid training inputs;
- zero or explicitly bounded training contradictions;
- performance above the predeclared baseline criterion;
- no resource-limit violations;
- no unresolved provenance warning that is being treated as verified independence;
- reproducibility across replay;
- a frozen candidate and untouched held-out set.

Thresholds must be set before the benchmark run, not adjusted after seeing results.

## 7. Required baselines and ablations

Compare on matched seeds, datasets, and compute budgets:

1. **Fixed grammar / fixed candidate list:** current finite-grammar style baseline.
2. **Random candidate search:** same candidate space and evaluation budget.
3. **Bounded enumeration without counterexample queries.**
4. **Enumeration with counterexample-guided refinement.**
5. **No-discovery control:** never adds a new candidate.
6. **Oracle upper bound:** scorer-only diagnostic, never an eligible competitor for deployment.

A later meta-grammar experiment must also compare against a system that cannot alter its grammar. Report paired differences and uncertainty intervals where appropriate, not just best-run scores.

## 8. Benchmark design and leakage prevention

Use at least four synthetic target families:
- periodic/modular relations;
- threshold and piecewise relations;
- compositions of known primitives;
- targets intentionally outside the initial grammar.

Partition by both random held-out inputs and a distribution-shift split. Include noisy labels, adversarially corrupted observations, sparse evidence, conflicting observations, and environments with no simple supported rule.

For every condition:
- use pre-registered seeds and trial counts;
- separate generator-visible training observations from scorer-only labels;
- keep test data out of candidate-generation logs;
- include simple baselines and a no-signal condition;
- report false acceptance, false rejection, abstention, held-out error, exact recovery where defined, candidate count, wall time, and execution count;
- report confidence intervals for rates and preserve per-trial machine-readable results.

The existing Phase 1C benchmark is useful but does **not** constitute open-ended operator discovery: its candidate grammar is finite and predefined.

## 9. Adversarial and provenance requirements

Reuse Phase 1D/1E only as the current untrusted provenance layer. The prototype must test:
- multiple reporter IDs with a common source;
- shared parent reports;
- duplicated observations and contradictory labels;
- fabricated independence-group metadata;
- poisoned examples and targeted counterexamples;
- replayed or reordered evidence.

Do not treat different cell IDs, source IDs, or declared independence groups as proof of independent experiments. If independent origin cannot be verified, report that uncertainty and run sensitivity analyses.

## 10. Stage gates

### Gate A — Specification freeze
Freeze the grammar, type system, resource limits, data split, metrics, baselines, seeds, and pass/fail thresholds before implementation results are inspected.

### Gate B — Minimal enumerator
Implement deterministic bounded enumeration, canonical candidate IDs, syntax costs, execution limits, and complete replay logs. No self-modifying grammar yet.

### Gate C — Falsification and held-out evaluation
Demonstrate that a candidate which fits training data but fails on held-out examples is rejected or explicitly marked uncertain. Include a target outside the grammar and verify abstention rather than a fabricated success.

### Gate D — Counterexample-guided revision
Allow new observations to eliminate or revise candidates while preserving prior versions and the causal record of each decision.

### Gate E — Controlled grammar extension (separate experiment)
Only after Gates A–D pass, allow proposals for grammar extensions. Each extension must be versioned, sandboxed, compared to a no-extension control, and evaluated on fresh held-out environments. It may be rejected; no automatic promotion is allowed.

### Gate F — Cross-cell transfer (separate experiment)
Only transfer candidates with reproducible definitions, test bundles, provenance-risk metadata, and independent validation evidence. Recipients must re-evaluate locally and may reject or counterexample the proposal. Agreement alone is insufficient.

## 11. Minimum acceptance criteria for the first implementation

The first implementation is eligible for a research claim only if:
- all tests pass on supported Python versions;
- candidate generation is deterministic for fixed seed and budget;
- every candidate is type-checked and resource-bounded;
- a deliberately overfit candidate fails a held-out test;
- an out-of-grammar target leads to abstention or an explicitly measured failure;
- no-discovery and random-search baselines are reported;
- all selection decisions can be replayed from saved inputs;
- evaluator-only truth cannot be accessed by the generator through the defined API;
- CI artifacts include configuration, seeds, metrics, and per-trial results.

Passing these criteria supports only the bounded claim: **“the prototype discovers a new expression relative to its initial candidate list and validates it on specified held-out synthetic tasks.”** It does not prove unrestricted operator invention or general intelligence.

## 12. Immediate next implementation task

Create a separate implementation issue/PR for Gate B only. Before coding, review the existing `heldout_benchmark.py` and `evidence_lab.py` interfaces and specify the exact observation contract and primitive grammar in tests. Do not combine enumerator implementation, meta-grammar revision, distributed trust, and experience transfer into one change.
