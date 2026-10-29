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
Candidate state is validated before commit. The full event bundle is hash-chained using SHA-256 over canonical JSON including previous_hash but excluding event_hash. Checkpoints hash serialized state. Atomic archive persistence writes a same-directory temporary file, fsyncs it, then replaces the destination. This is not a digital signature and does not authenticate event authorship.

## Explicit non-goals
No claims about AGI, consciousness, general learning, biological fidelity, quantum effects, emergent semantics, or scalability follow from this contract.
