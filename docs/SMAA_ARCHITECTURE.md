# SMAA 0.1 — Functional Self-Model & Awareness Architecture

SMAA is a vertical subsystem across the seven functional layers of the host digital-cell architecture. It is not an eighth layer and does not assert phenomenal consciousness.

## Implemented
- Self-state: versioned network identity, member registry, capability evidence, knowledge claims, resources, unknowns and assumptions.
- Identity continuity: stable network identifier plus join/deactivation history and membership reconstruction.
- Agency provenance: append-only events record actor, event type, tick and payload. Actor attribution is not proof of external physical causation.
- Workspace boundary: a spawned process per cell stores private observations and exports only a small allow-listed summary; the network API also rejects raw observations, private memory, hidden labels and unknown fields.
- Metacognition: forecast records, Brier components, aggregate Brier score and expected calibration error.
- Autobiographical history: canonical JSON SHA-256 hash-chained event ledger.
- Social self-model: claims retain owner, evidence references and verification status.
- Self-revision: reason-bearing, versioned revisions with audit events.

## Trust limits
The reference includes one spawned OS process per cell, so the parent receives only explicit summary messages rather than the child observation store. This is process separation, not a hardened sandbox: a compromised worker can still use the host account's permissions and resources. Production requires OS/container sandboxing, authenticated schema-validated transport, quotas and threat-model-specific controls. Hash chaining detects modification relative to a trusted head; it does not authenticate authorship or prevent complete chain rewriting. Actor labels are caller assertions until authenticated.

## Prediction limits
predict_state is a transparent baseline, not a trained or discovered model. It reports registered state and action metadata. Error probes validate comparison bookkeeping, not general predictive competence.

## Eight probes
1. self/other membership distinction; 2. actor/event attribution; 3. continuity after deactivation; 4. explicit unknown tracking; 5. prediction recording/calibration; 6. self-state prediction error; 7. social knowledge provenance; 8. versioned self-model revision.

These are executable software probes, not evidence of human-like consciousness.

## Stage status
- SMAA-0 schemas, event ledger and stable IDs: implemented.
- SMAA-1 local self-state: partial; worker processes hold private observations, while the full per-cell local self-model and durable memory lifecycle remain future work.
- SMAA-2 self/other and actor attribution: process/API/event-level implementation; a minimal self-model-gated attempt/abstain policy is included; causal held-out intervention benchmark remains future work.
- SMAA-3 history/continuity: in-memory event history; durable persistence remains future work.
- SMAA-4 self-prediction/error: baseline bookkeeping; learned predictive model remains future work.
- SMAA-5 metacognition/calibration: metrics and forecast records implemented; large-sample validation remains future work.
- SMAA-6 social boundaries: claim/API level; cryptographic identity and process isolation remain future work.
- SMAA-7 structural revision: versioned model revision; sandboxed grammar/code evolution remains future work.
- SMAA-8 host integration: deliberately not merged into GDC 0.2.1 experiment; isolated reference branch only.

Runtime uses Python standard library only.
