# Evo-Geo — Phase 0: Deterministic Geometric Substrate

**Status:** reference implementation under validation. This project does not claim AGI, consciousness, learning, or emergent intelligence.

Phase 0 defines a deterministic integer-lattice world, explicit invariants, reproducible transitions, a SHA-256 event chain, checkpoints, atomic archive persistence, and automated tests. Later phases must be justified by experiments, not by reinterpreting these mechanics as intelligence.

## Quick start

Requires Python 3.11+; runtime has no third-party dependencies.

```bash
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
python -m evo_geo
```

## Core contract

- Q16.16 integer coordinates (`Q = 65,536`); no floating point in state transitions.
- Twenty fixed initial points on a radius-2.5 ring; first floor(20%) of sorted IDs are special.
- Each step computes movement from an immutable start-of-step snapshot.
- Every existing vertex receives exactly one bounded action.
- IDs are monotonic; replication requests are processed in canonical request-ID order.
- Undirected graph edges use hysteresis: add at distance <= 0.9, remove at distance >= 1.1.
- Events use canonical JSON and SHA-256 chaining; checkpoints are state-hashed and bound to the matching committed snapshot.
- Archive schema v2 stores the exact execution contract; verification and replay validate state under that contract and audit event semantics against committed snapshots.
- POSIX persistence fsyncs the temporary file, atomically replaces the destination, then fsyncs the containing directory. A failure after replacement can leave the new archive visible while crash durability remains uncertain; reopen and verify rather than assuming the old file survived.
- Invalid inputs must not mutate live state or append events.

See [SPEC.md](SPEC.md) for normative behavior and [docs/VALIDATION.md](docs/VALIDATION.md) for test scope and limitations. Passing tests validate only tested properties; they do not prove AGI, general learning, or physical realism.
