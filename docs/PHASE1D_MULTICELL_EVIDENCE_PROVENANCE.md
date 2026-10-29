# Phase 1D — Multi-cell evidence provenance and conflict preservation

## Purpose

This phase adds a small, deterministic data model for evidence reports from multiple
digital cells. It is a protocol primitive, not a distributed-consensus algorithm.

## Report fields

Each report carries a reporter ID, source ID, experiment ID, claim ID, value,
declared independence group, and parent report IDs. A canonical JSON representation
is hashed with SHA-256 to obtain a stable content identifier. Identical report
payloads are deduplicated; distinct reports remain available for inspection.

## Conflict handling

`assess_claim` groups reports by claim and reports all distinct values. It does not
select a winner, average contradictory values, or erase minority reports. It also
reports counts of reporter IDs, source IDs, and declared independence groups so
that a large number of reports from one lineage is not mistaken for independent
replication.

## Threat model and limits

- The independence group is asserted metadata. It is not proof that sources are
  independent or that reporters are honest.
- A SHA-256 content digest detects payload changes when the expected digest is
  trusted; it does not authenticate a cell or provide a digital signature.
- This phase does not implement Byzantine fault tolerance, Sybil resistance,
  network transport, trusted timestamps, or causal-consistency guarantees.
- Coordinated reporters can lie about their source or independence group unless
  identity and source attestations are authenticated externally.
- Conflicts are preserved, not resolved. Resolution requires independent
  experiments and explicit domain-specific evaluation.

## Reproducible checks

Run:

```bash
python -m unittest discover -s tests -v
```

The tests cover deterministic report IDs, contradictory claims, shared lineage,
duplicate reports, filtering by claim, and invalid metadata. Passing tests establish
these software properties only; they do not establish adversarial security or
scientific truth.

## Next gates

1. Add authenticated identities/signatures and tamper-evident lineage.
2. Define adversarial multi-proposer scenarios (including shared-source and Sybil
   cases) with explicit expected outcomes.
3. Add independently generated evidence and a policy that defers rather than
   votes when independence cannot be established.
4. Only then connect this report model to validated experience transfer.
