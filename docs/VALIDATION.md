# Phase 0 validation record

Tests cover numeric and geometry boundaries, strict state parsing, deterministic transitions, transactional rejection, replication, checkpoint-to-snapshot binding, non-default contract round trips and replay, hash-resealed semantic event tampering, continuity/completeness of edge events, and storage failure injection before and after replacement including POSIX directory-fsync failure.

A passing suite means only that the checked properties held for these cases and runtime. It is not a proof for all possible inputs, platforms, filesystems, or future changes.

Known limits:
- The influence kernel is linear in squared distance by design; it is not Gaussian/exponential.
- `Archive.verify_genesis_anchor(expected_sha256)` can bind the first recorded start-state to an externally trusted digest. The digest must be provisioned through an independent trusted channel; computing a digest from the archive being verified does not authenticate its origin. This is a hash anchor, not a signature or identity proof.
- `save_atomic(path, expected_current_sha256=...)` serializes writers with an advisory OS lock and supports compare-and-swap against the exact current file bytes. A stale writer is rejected when it supplies the digest of the version it read. Unconditional calls (omitting the expected digest) still intentionally allow last-writer-wins behavior. Lock semantics depend on OS/filesystem support; network filesystems may differ.
- Full start-state and committed-state snapshots are recorded per step; replay and semantic checks reject tested malformed/resealed logs. Process-exit tests cover selected pre-replace and post-replace points, but do not simulate power loss, storage-controller caches, physical disk failure, or every filesystem implementation.
- A second independent human code review and scalability benchmark have not been completed.
- No learning, evolution, semantic transfer, consciousness, or AGI capability is implemented or evidenced.

Run `python -m unittest discover -s tests -v` and `python -m evo_geo`. The CI run URL and commit must be recorded before claiming CI acceptance.
