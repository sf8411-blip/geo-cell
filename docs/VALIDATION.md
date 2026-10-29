# Phase 0 validation record

Tests cover signed ties-to-even rounding, integer square-root bounds, radial clipping over a finite grid, initial-state invariants, strict state round-trip, deterministic repeated execution, invalid-action rollback, replication ID monotonicity, conflicting-request rollback, hash-chain tampering, checkpoint validation, atomic archive save/load, tampered archive rejection, and a 50-step invariant run.

A passing suite means only that the checked properties held for these cases and runtime. It is not a proof for all possible inputs, platforms, filesystems, or future changes.

Known limits:
- The influence kernel is linear in squared distance by design; it is not Gaussian/exponential.
- Archive atomic replacement assumes a single filesystem and does not promise survival of every hardware/filesystem failure or concurrent writers.
- Full-state snapshots are recorded at STEP_COMMITTED, and a replay-from-checkpoint API is implemented and unit-tested. Crash-injection testing and replay under malformed-but-rehashed logs remain follow-up acceptance work.
- No independent code audit or scalability benchmark has been completed.
- No learning, evolution, semantic transfer, consciousness, or AGI capability is implemented or evidenced.

Run `python -m unittest discover -s tests -v` and `python -m evo_geo`. The CI run URL and commit must be recorded before claiming CI acceptance.
