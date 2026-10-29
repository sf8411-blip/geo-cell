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

Input validation, candidate-state construction, event-bundle sealing, and checkpoint staging occur before publishing the step. Publication assigns staged events, staged checkpoints, then the new state; this is a single-threaded commit convention, not a database transaction or thread-safe atomic primitive. Durable archive save writes and fsyncs a same-directory temporary file, atomically replaces the destination, then fsyncs the parent directory on POSIX. If a failure occurs after replacement, the new archive may be visible while crash durability is uncertain. Concurrent writers and hardware/filesystem failure modes remain outside the guarantee.

## Audit caveat

SHA-256 chaining detects content modification relative to a trusted chain head. It is not a digital signature, does not establish event authorship, and does not prevent an attacker from rewriting the entire archive and recomputing every hash.
