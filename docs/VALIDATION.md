# Phase 0 validation record

Tests cover numeric and geometry boundaries, strict state parsing, deterministic transitions, transactional rejection, replication, checkpoint-to-snapshot binding, non-default contract round trips and replay, hash-resealed semantic event tampering, continuity/completeness of edge events, and storage failure injection before and after replacement including POSIX directory-fsync failure.

A passing suite means only that the checked properties held for these cases and runtime. It is not a proof for all possible inputs, platforms, filesystems, or future changes.

Known limits:
- The influence kernel is linear in squared distance by design; it is not Gaussian/exponential.
- `Archive.verify_genesis_anchor(expected_sha256)` can bind the first recorded start-state to an externally trusted digest. The digest must be provisioned through an independent trusted channel; computing a digest from the archive being verified does not authenticate its origin. This is a hash anchor, not a signature or identity proof.
- `save_atomic(path, expected_current_sha256=...)` serializes cooperative writers with an advisory OS lock and supports compare-and-swap against exact current file bytes. Competing-process tests require exactly one writer with the same expected digest to succeed. The lock path must remain persistent; symlinks are rejected where `O_NOFOLLOW` is supported. Old temporary files matching this archive's private temp-name pattern are cleaned under the lock before a new write. Unconditional calls (omitting the expected digest) still intentionally allow last-writer-wins behavior. Advisory lock semantics remain OS/filesystem-dependent, especially on network filesystems, and non-cooperating writers can bypass them.
- Full start-state and committed-state snapshots are recorded per step; replay and semantic checks reject tested malformed/resealed logs. Process-exit tests cover selected pre-replace and post-replace points, but do not simulate power loss, storage-controller caches, physical disk failure, or every filesystem implementation.
- Automated coverage now includes competing OS processes, stale compare-and-swap rejection, symlink-lock rejection where supported, and cleanup of temp debris left by a hard process exit. These tests are not a proof of power-loss durability, storage-controller behavior, or correctness on every filesystem.
- Cross-platform CI and an independent human review are separate acceptance gates; green tests do not count as an independent review. Scalability benchmarks remain uncompleted.
- No learning, evolution, semantic transfer, consciousness, or AGI capability is implemented or evidenced.

Run `python -m unittest discover -s tests -v` and `python -m evo_geo`. The CI run URL and commit must be recorded before claiming CI acceptance.
