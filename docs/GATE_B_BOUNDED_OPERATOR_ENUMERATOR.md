# Gate B — Deterministic bounded operator enumerator

## Status and scope
This is a bounded symbolic-search prototype, not open-ended discovery, self-modifying grammar, or multi-cell transfer.

## Observation contract
- Inputs are integers in [-16, 16]; Boolean values are rejected as integers.
- Labels are integer 0 or 1; Boolean labels are rejected.
- Repeated x values with conflicting labels cause abstention; no last-write-wins behavior.
- The search API sees only supplied training observations and has no oracle or held-out-label parameter.
- At least four distinct inputs are required by default.

## Frozen primitive grammar
- Leaves: x and integer constants -2 through 4.
- Integer operators: addition, subtraction, multiplication, and modulo by a positive literal.
- Boolean operators: equality, less-than, NOT, AND, OR.
- Candidates run in a closed AST interpreter; generated source is never executed.
- Output is restricted to binary integer/Boolean predictions.
- Syntax cost is one per leaf/operator. Canonical text and SHA-256 IDs are versioned.

## Search and decision
Candidates are enumerated deterministically in syntax-cost order. Gate B hard-caps syntax cost at 4 and candidate count at max_candidates to keep this initial search finite and auditable. The simplest exact-fit expression absent from the initial named list is returned. If no such expression exists or evidence is contradictory/sparse, the engine abstains. Counterexamples can reject a frozen candidate without changing the grammar.

## Limits and next tests
Syntactic novelty relative to a short initial list is not mathematical novelty. Exact fit can overfit; Gate C must evaluate frozen candidates on held-out and distribution-shift examples, including out-of-grammar and no-signal targets. Candidate caps impose search-order bias. Hashes identify canonical text but do not prove correctness or provenance. No grammar mutation, automatic promotion, network access, or cross-cell sharing is implemented.
