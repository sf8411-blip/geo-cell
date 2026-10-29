# Architecture and trust boundaries

```text
StepInputs
  -> validate inputs (reject without mutation)
  -> immutable start-of-step snapshot
  -> calculate all movement proposals
  -> radial boundary clipping
  -> canonical replication request processing
  -> recompute special membership
  -> update hysteretic undirected graph
  -> validate candidate state
  -> prepare complete hash-chained event bundle
  -> append event bundle and swap live state
  -> periodic state checkpoint
```

## Module boundaries

- `evo_geo/core.py`: numeric contract, state, geometry, transition engine, archive, serialization.
- `evo_geo/replay.py`: checkpoint verification and committed-snapshot replay.
- `tests/`: executable contract tests.
- `.github/workflows/tests.yml`: CI matrix for Python 3.11–3.13.

## Transaction caveat

Input validation, candidate-state construction, and event-bundle preparation occur before the live state is replaced. The in-memory event append and state swap are separate Python operations, not a database transaction. Periodic checkpoint creation occurs after commit. If checkpoint creation fails, the step may already be committed. Durable archive save uses temporary-file + fsync + atomic replace, but concurrent writers and all hardware failure modes are outside this guarantee.

## Audit caveat

SHA-256 chaining detects content modification relative to a trusted chain head. It is not a digital signature, does not establish event authorship, and does not prevent an attacker from rewriting the entire archive and recomputing every hash.
