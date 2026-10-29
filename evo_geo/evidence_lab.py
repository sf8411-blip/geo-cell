"""Evidence-based experience evaluation lab (simulation only).

Cells independently evaluate candidate rules from observations. A benchmark
oracle labels rules only for scoring; simulated cells do not receive that label.
Counterexamples can overturn prior acceptance. This is not a learning/AGI claim.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import random
from typing import Iterable

CONTRACT_VERSION = 1
RULES = ("parity", "constant_zero", "inverted_parity")


def predict(rule: str, x: int) -> int:
    if rule == "parity":
        return x % 2
    if rule == "constant_zero":
        return 0
    if rule == "inverted_parity":
        return 1 - (x % 2)
    raise ValueError(f"unknown rule: {rule}")


def oracle_truth(rule: str, domain_size: int = 32) -> bool:
    """Evaluator-only benchmark label; never supplied to Cell."""
    return all(predict(rule, x) == x % 2 for x in range(domain_size))


@dataclass(frozen=True)
class Observation:
    x: int
    y: int

    def valid(self) -> bool:
        return (
            isinstance(self.x, int) and not isinstance(self.x, bool)
            and 0 <= self.x <= 31
            and isinstance(self.y, int) and not isinstance(self.y, bool)
            and self.y in (0, 1)
        )


@dataclass(frozen=True)
class EvidenceMessage:
    message_id: str
    kind: str  # proposal, evidence, counterexample
    proposer: int
    contract_version: int
    hypothesis_id: str
    rule: str
    parent_id: str | None
    observations: tuple[Observation, ...]

    def canonical(self) -> bytes:
        payload = {
            "message_id": self.message_id,
            "kind": self.kind,
            "proposer": self.proposer,
            "contract_version": self.contract_version,
            "hypothesis_id": self.hypothesis_id,
            "rule": self.rule,
            "parent_id": self.parent_id,
            "observations": [{"x": o.x, "y": o.y} for o in self.observations],
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


@dataclass
class LocalHypothesis:
    rule: str
    proposer: int
    proposal_id: str
    observations: list[Observation] = field(default_factory=list)
    status: str = "pending"
    retractions: int = 0

    def evaluate(self, min_support: int) -> str:
        if any(predict(self.rule, observation.x) != observation.y for observation in self.observations):
            if self.status == "accepted":
                self.retractions += 1
            self.status = "rejected"
        elif len({observation.x for observation in self.observations}) >= min_support:
            self.status = "accepted"
        else:
            self.status = "pending"
        return self.status


@dataclass
class EvidenceCell:
    cell_id: int
    contract_version: int = CONTRACT_VERSION
    hypotheses: dict[str, LocalHypothesis] = field(default_factory=dict)
    seen: set[str] = field(default_factory=set)
    pending: dict[str, EvidenceMessage] = field(default_factory=dict)
    rejected_messages: int = 0
    duplicate_messages: int = 0
    accepted_false_events: int = 0

    def receive(self, message: EvidenceMessage, min_support: int = 3) -> str:
        if message.message_id in self.seen or message.message_id in self.pending:
            self.duplicate_messages += 1
            return "duplicate"
        if (
            message.contract_version != self.contract_version
            or message.kind not in ("proposal", "evidence", "counterexample")
            or message.rule not in RULES
            or not message.hypothesis_id
            or any(not obs.valid() for obs in message.observations)
            or (message.kind == "proposal" and message.parent_id is not None)
            or (message.kind != "proposal" and not message.parent_id)
        ):
            self.rejected_messages += 1
            return "invalid"
        if message.kind != "proposal" and message.hypothesis_id not in self.hypotheses:
            self.pending[message.message_id] = message
            return "buffered"
        self._apply(message, min_support)
        self._drain(min_support)
        return "accepted"

    def _apply(self, message: EvidenceMessage, min_support: int) -> None:
        self.seen.add(message.message_id)
        if message.kind == "proposal":
            self.hypotheses[message.hypothesis_id] = LocalHypothesis(
                rule=message.rule, proposer=message.proposer, proposal_id=message.message_id
            )
        else:
            hypothesis = self.hypotheses[message.hypothesis_id]
            # Preserve every observation. Conflicting reports for the same x must
            # not overwrite one another and erase a counterexample.
            hypothesis.observations.extend(message.observations)
            hypothesis.evaluate(min_support)

    def _drain(self, min_support: int) -> None:
        progress = True
        while progress:
            progress = False
            for message_id, message in list(self.pending.items()):
                if message.hypothesis_id in self.hypotheses:
                    del self.pending[message_id]
                    self._apply(message, min_support)
                    progress = True


def _id(seed: int, *parts: object) -> str:
    return hashlib.sha256((str(seed) + "|" + "|".join(map(str, parts))).encode()).hexdigest()[:24]


def build_scenario(cell_count: int, seed: int) -> tuple[list[EvidenceMessage], list[EvidenceMessage]]:
    """Return proposals/evidence and later counterexamples; includes a deceptive case."""
    rng = random.Random(seed)
    initial: list[EvidenceMessage] = []
    counterexamples: list[EvidenceMessage] = []
    for proposer in range(cell_count):
        for rule in RULES:
            hid = f"hyp-{proposer}-{rule}"
            proposal_id = _id(seed, "proposal", proposer, rule)
            initial.append(EvidenceMessage(
                proposal_id, "proposal", proposer, CONTRACT_VERSION, hid, rule, None, ()
            ))
            if rule == "constant_zero":
                # Deliberately select only even inputs: a false rule looks plausible.
                xs = [2 * rng.randrange(0, 16) for _ in range(3)]
            else:
                xs = rng.sample(range(32), 3)
            obs = tuple(Observation(x, x % 2) for x in xs)
            initial.append(EvidenceMessage(
                _id(seed, "evidence", proposer, rule), "evidence", proposer,
                CONTRACT_VERSION, hid, rule, proposal_id, obs
            ))
            if not oracle_truth(rule):
                x = next(x for x in range(32) if predict(rule, x) != x % 2)
                counterexamples.append(EvidenceMessage(
                    _id(seed, "counterexample", proposer, rule), "counterexample",
                    proposer, CONTRACT_VERSION, hid, rule,
                    _id(seed, "evidence", proposer, rule), (Observation(x, x % 2),)
                ))
    return initial, counterexamples


def run_evidence_experiment(
    cell_count: int = 8,
    seed: int = 20261030,
    min_support: int = 3,
    partitioned_cell: int | None = None,
) -> dict:
    """Run independent proposal/evidence delivery, partition, and counterexample recovery."""
    if cell_count < 2:
        raise ValueError("cell_count must be >= 2")
    if min_support < 1:
        raise ValueError("min_support must be >= 1")
    if partitioned_cell is not None and not 0 <= partitioned_cell < cell_count:
        raise ValueError("partitioned_cell is out of range")

    cells = [EvidenceCell(i) for i in range(cell_count)]
    initial, counterexamples = build_scenario(cell_count, seed)
    rng = random.Random(seed ^ 0xC0FFEE)
    initial.sort(key=lambda m: (0 if m.kind == "proposal" else 1, m.proposer, m.rule))
    # For a partitioned cell, hold all traffic until the recovery phase.
    for message in initial:
        targets = list(range(cell_count))
        rng.shuffle(targets)
        for target in targets:
            if target == partitioned_cell:
                continue
            cells[target].receive(message, min_support)
            if (target + len(message.message_id)) % 11 == 0:
                cells[target].receive(message, min_support)

    before = _score(cells, min_support)
    # Send counterexamples; then heal partition and replay queued history.
    for message in counterexamples:
        for target, cell in enumerate(cells):
            if target == partitioned_cell:
                continue
            cell.receive(message, min_support)
    if partitioned_cell is not None:
        # The returning cell gets the full ordered history. Proposals first, then evidence,
        # then counterexamples, so it can reconstruct local decisions from scratch.
        returning = cells[partitioned_cell]
        for message in initial:
            returning.receive(message, min_support)
        for message in counterexamples:
            returning.receive(message, min_support)

    after = _score(cells, min_support)
    return {
        "cell_count": cell_count,
        "seed": seed,
        "min_support": min_support,
        "partitioned_cell": partitioned_cell,
        "initial": before,
        "after_counterexamples_and_rejoin": after,
        "recovery_complete": all(
            len(cell.hypotheses) == cell_count * len(RULES) for cell in cells
        ),
        "duplicate_messages": sum(c.duplicate_messages for c in cells),
        "invalid_messages_rejected": sum(c.rejected_messages for c in cells),
        "pending_messages": sum(len(c.pending) for c in cells),
    }


def _score(cells: Iterable[EvidenceCell], min_support: int) -> dict:
    total_true = total_false = accepted_true = accepted_false = rejected_false = rejected_true = 0
    false_acceptance_rate_n = false_acceptance_rate_d = 0
    false_rejection_rate_n = false_rejection_rate_d = 0
    retractions = 0
    for cell in cells:
        for hypothesis in cell.hypotheses.values():
            truth = oracle_truth(hypothesis.rule)
            accepted = hypothesis.status == "accepted"
            retractions += hypothesis.retractions
            if truth:
                total_true += 1
                false_rejection_rate_d += 1
                if accepted:
                    accepted_true += 1
                elif hypothesis.status == "rejected":
                    rejected_true += 1
                    false_rejection_rate_n += 1
            else:
                total_false += 1
                false_acceptance_rate_d += 1
                if accepted:
                    accepted_false += 1
                    false_acceptance_rate_n += 1
                elif hypothesis.status == "rejected":
                    rejected_false += 1
    return {
        "hypotheses_seen": total_true + total_false,
        "true_hypotheses": total_true,
        "false_hypotheses": total_false,
        "accepted_true": accepted_true,
        "accepted_false": accepted_false,
        "correct_rejections_of_false": rejected_false,
        "rejected_true": rejected_true,
        "false_acceptance_rate": (
            false_acceptance_rate_n / false_acceptance_rate_d if false_acceptance_rate_d else 0.0
        ),
        "false_rejection_rate": (
            false_rejection_rate_n / false_rejection_rate_d if false_rejection_rate_d else 0.0
        ),
        "retractions": retractions,
        "min_support": min_support,
    }


def run_scale_sweep(cell_counts=(2, 4, 8, 16), seed: int = 20261030) -> list[dict]:
    return [
        run_evidence_experiment(n, seed, partitioned_cell=n - 1)
        for n in cell_counts
    ]


def main() -> None:
    print(json.dumps(run_scale_sweep(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
