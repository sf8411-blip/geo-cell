# Phase 1 Network Protocol Lab

## Purpose

This is a deterministic, falsifiable **simulation** of experience-message delivery among independent in-memory cells. It is intentionally isolated in `evo_geo/network_lab.py`; it does not change the Phase 0 engine, archive format, or reference tests.

## Protocol model

Each immutable message has a unique ID, origin cell, sequence, contract version, causal parent ID, and bounded integer delta. A receiving cell maintains its own accepted-message ledger, pending causal descendants, rejection count, duplicate count, and byte count. Duplicate messages are idempotent. Descendants arriving before their parent are buffered and applied after the missing ancestry arrives. Unknown contract versions and malformed payloads are rejected.

The experiment schedules deterministic jitter, duplicate delivery, and a partition affecting the final cell, followed by delayed delivery on rejoin. Every cell is compared with a centralized reference that processes the same canonical causal chain. A scale sweep defaults to 2, 4, 8, and 16 simulated cells.

## Run

```bash
python -m unittest discover -s tests -v
python -m evo_geo.network_lab
```

The JSON output records convergence, accepted-event counts, state divergence, pending messages, rejected messages, duplicate deliveries, bytes sent/received, and the final delivery tick used as a simple convergence-time proxy.

## Falsification and interpretation

A run fails its convergence assertion if any cell's accepted IDs or accumulated value differs from the centralized reference after the delivery queue is drained. The test suite also checks idempotency, causal buffering, contract-version rejection, malformed payload rejection, and seeded reproducibility.

**Important limits:** the scheduler is an in-process deterministic model. The reported tick is not wall-clock latency; byte counts are serialized payload bytes and exclude transport framing, encryption, acknowledgements, retries at a real network layer, and CPU/memory overhead. The model does not implement signatures, Byzantine consensus, membership discovery, protocol negotiation, persistent per-cell storage, real packet loss, physical devices, or hundreds of networked machines. It cannot establish decentralized intelligence or AGI. A scale sweep reports the requested sizes; it does not automatically prove the maximum safe scale. The current workload is expected to converge under eventual delivery; stronger faults and conflicting valid histories are future protocol questions, not silently treated as solved.
