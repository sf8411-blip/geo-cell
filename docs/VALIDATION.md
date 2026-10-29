# Phase 0 validation record

Tests cover numeric and geometry boundaries, strict state parsing, deterministic transitions, transactional rejection, replication, checkpoint-to-snapshot binding, non-default contract round trips and replay, hash-resealed semantic event tampering, continuity/completeness of edge events, and storage failure injection before and after replacement including POSIX directory-fsync failure.

A passing suite means only that the checked properties held for these cases and runtime. It is not a proof for all possible inputs, platforms, filesystems, or future changes.

Known limits:
- The influence kernel is linear in squared distance by design; it is not Gaussian/exponential.
- Archive atomic replacement assumes a single filesystem and does not promise survival of every hardware/filesystem failure or concurrent writers.
- Full start-state and committed-state snapshots are recorded per step; replay and semantic checks reject tested malformed/resealed logs. Fault injection covers selected persistence points, not every possible syscall, power-loss mode, filesystem, or concurrent-writer race.
- A second independent human code review and scalability benchmark have not been completed.
- No learning, evolution, semantic transfer, consciousness, or AGI capability is implemented or evidenced.

Run `python -m unittest discover -s tests -v` and `python -m evo_geo`. The CI run URL and commit must be recorded before claiming CI acceptance.
