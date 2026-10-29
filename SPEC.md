# Phase 0 normative contract

## Scope
A deterministic geometric substrate only. No learner, optimizer, neural network, language model, consciousness model, or AGI claim is included.

## Numeric model
Coordinates are integers with Q=65,536 lattice units per world unit. Division uses round-to-nearest, ties-to-even, symmetrically for negative values. Geometry comparisons use squared integer distances. Transition logic must not use floating-point arithmetic; bool is not accepted as an integer input.

## Initial state
Twenty fixed integer coordinate pairs approximate a radius-2.5 ring. IDs are 1..20. The first floor(N/5) IDs in ascending order are special. IDs are never reused.

## Movement
A step requires exactly one bounded (dx,dy) tuple per vertex present at step start. Every proposal is computed from the immutable start-of-step snapshot, then applied in ascending ID order. Special vertices contribute using a compact linear kernel: if d² < 2H², weight = Q - round_even(Q*d²/(2H²)); otherwise weight = 0. Contribution per component is round_even(weight*action/(2Q)). This is a linear-in-squared-distance kernel, not Gaussian or exponential. Proposed coordinates outside the outer disk are deterministically clipped to the disk.

## Graph
For each unordered pair in ascending ID order: add absent edge when d² <= 0.9²; remove present edge when d² >= 1.1²; otherwise preserve status. Edges are canonical (min_id,max_id) tuples.

## Replication
Requests are sorted by nonempty request ID. Duplicate IDs with different payloads reject the whole step before mutation. Matching previously processed requests are idempotent. Unknown parent, invalid radius, out-of-range coordinates, or duplicate position yield a recorded rejection. Accepted IDs use the monotonic counter; new vertices do not move during their birth step.

## Transaction and audit
Candidate state is validated before commit. Each step records its start snapshot, the execution contract, semantic events, and a committed state snapshot. The full event bundle is hash-chained using SHA-256 over canonical JSON including previous_hash but excluding event_hash; verification checks event structure and transition deltas against start/committed snapshots. Checkpoints hash serialized state and must match the same-step committed snapshot. Archive schema v2 persists the exact contract. Persistence writes and fsyncs a same-directory temporary file, atomically replaces the destination, and fsyncs the parent directory on POSIX. A persistent advisory lock on a regular lock file serializes cooperative writers; symlink lock paths are rejected where the OS supports no-follow opens. The lock file must not be removed or replaced while clients may use it. Callers that pass `expected_current_sha256` get compare-and-swap behavior, with `"missing"` denoting an absent destination; competing cooperative writers using the same prior digest cannot both commit. Omitting that argument is fail-closed for an existing destination; explicit `None` opts into unconditional replacement and can still lose stale updates. Before writing, stale temp files matching the destination's private temp-name pattern are removed while holding the lock. Locks remain advisory and filesystem-dependent; this is not a distributed-lock protocol. `Archive.verify_genesis_anchor(expected_sha256)` compares the first recorded start-state digest against a separately provisioned trusted SHA-256 anchor. Neither hash chaining nor an untrusted self-computed anchor authenticates event authorship; signature-based identity is out of scope.

## Explicit non-goals
No claims about AGI, consciousness, general learning, biological fidelity, quantum effects, emergent semantics, or scalability follow from this contract.
