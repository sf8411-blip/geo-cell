"""Deterministic, falsifiable network-protocol lab for Phase 1.

This is a simulation harness, not a transport, consensus protocol, or claim of
real-device scale. Messages carry immutable IDs, contract versions and causal
parent IDs. A receiver buffers out-of-order descendants and applies each valid
message at most once.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import random
from typing import Iterable


@dataclass(frozen=True)
class ExperienceMessage:
    message_id: str
    origin_cell: int
    sequence: int
    contract_version: int
    parent_id: str | None
    delta: int

    def canonical(self) -> bytes:
        return json.dumps(
            {
                "message_id": self.message_id,
                "origin_cell": self.origin_cell,
                "sequence": self.sequence,
                "contract_version": self.contract_version,
                "parent_id": self.parent_id,
                "delta": self.delta,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def digest(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()


@dataclass
class Cell:
    cell_id: int
    contract_version: int = 1
    accepted: dict[str, ExperienceMessage] = field(default_factory=dict)
    pending: dict[str, ExperienceMessage] = field(default_factory=dict)
    rejected: int = 0
    duplicates: int = 0
    received_bytes: int = 0

    @property
    def value(self) -> int:
        return sum(message.delta for message in self.accepted.values())

    def receive(self, message: ExperienceMessage) -> str:
        self.received_bytes += len(message.canonical())
        if message.message_id in self.accepted or message.message_id in self.pending:
            self.duplicates += 1
            return "duplicate"
        if not _valid_message_shape(message):
            self.rejected += 1
            return "invalid"
        if message.contract_version != self.contract_version:
            self.rejected += 1
            return "version_conflict"
        if message.parent_id is not None and message.parent_id not in self.accepted:
            self.pending[message.message_id] = message
            return "buffered"
        self._apply(message)
        self._drain_pending()
        return "accepted"

    def _apply(self, message: ExperienceMessage) -> None:
        self.accepted[message.message_id] = message

    def _drain_pending(self) -> None:
        progressed = True
        while progressed:
            progressed = False
            for message_id, message in list(self.pending.items()):
                if message.parent_id is None or message.parent_id in self.accepted:
                    del self.pending[message_id]
                    self._apply(message)
                    progressed = True


def _valid_message_shape(message: ExperienceMessage) -> bool:
    return (
        isinstance(message.message_id, str)
        and bool(message.message_id)
        and isinstance(message.origin_cell, int)
        and not isinstance(message.origin_cell, bool)
        and message.origin_cell >= 0
        and isinstance(message.sequence, int)
        and not isinstance(message.sequence, bool)
        and message.sequence >= 1
        and isinstance(message.contract_version, int)
        and not isinstance(message.contract_version, bool)
        and message.contract_version >= 1
        and (message.parent_id is None or (isinstance(message.parent_id, str) and bool(message.parent_id)))
        and isinstance(message.delta, int)
        and not isinstance(message.delta, bool)
        and -100 <= message.delta <= 100
    )


@dataclass(frozen=True)
class Delivery:
    tick: int
    target_cell: int
    message: ExperienceMessage


def make_chain(event_count: int, seed: int, contract_version: int = 1) -> list[ExperienceMessage]:
    if event_count < 1:
        raise ValueError("event_count must be >= 1")
    rng = random.Random(seed)
    messages = []
    parent = None
    for sequence in range(1, event_count + 1):
        message_id = hashlib.sha256(f"{seed}:{sequence}:{parent}".encode()).hexdigest()[:24]
        message = ExperienceMessage(
            message_id=message_id,
            origin_cell=(sequence - 1) % 3,
            sequence=sequence,
            contract_version=contract_version,
            parent_id=parent,
            delta=rng.choice((-3, -2, -1, 1, 2, 3)),
        )
        messages.append(message)
        parent = message_id
    return messages


def centralized_reference(messages: Iterable[ExperienceMessage], contract_version: int = 1) -> tuple[set[str], int]:
    accepted: set[str] = set()
    value = 0
    for message in messages:
        if not _valid_message_shape(message) or message.contract_version != contract_version:
            continue
        if message.parent_id is not None and message.parent_id not in accepted:
            raise ValueError("central reference received a non-causal message order")
        if message.message_id not in accepted:
            accepted.add(message.message_id)
            value += message.delta
    return accepted, value


def run_experiment(
    cell_count: int = 8,
    event_count: int = 40,
    seed: int = 20261030,
    partition_start: int = 8,
    partition_end: int = 13,
) -> dict:
    """Run deterministic delivery faults and return auditable metrics.

    During [partition_start, partition_end), the final cell is disconnected.
    Messages to it are delayed until rejoin. Other deliveries have bounded
    jitter and deliberate duplicates. The final drain allows causal buffers to
    settle. This models protocol behavior, not physical networking.
    """
    if cell_count < 2:
        raise ValueError("cell_count must be >= 2")
    if event_count < 1:
        raise ValueError("event_count must be >= 1")
    if partition_start < 0 or partition_end < partition_start:
        raise ValueError("invalid partition interval")

    messages = make_chain(event_count, seed)
    cells = [Cell(i) for i in range(cell_count)]
    rng = random.Random(seed ^ 0x51A7)
    deliveries: list[Delivery] = []
    bytes_sent = 0
    for index, message in enumerate(messages):
        for target in range(cell_count):
            delay = rng.randrange(0, 4)
            tick = index + delay
            if target == cell_count - 1 and partition_start <= tick < partition_end:
                tick = partition_end + (index % 3)
            deliveries.append(Delivery(tick, target, message))
            bytes_sent += len(message.canonical())
            if (index + target) % 7 == 0:
                deliveries.append(Delivery(tick + 1, target, message))
                bytes_sent += len(message.canonical())

    deliveries.sort(key=lambda d: (d.tick, d.target_cell, d.message.sequence, d.message.message_id))
    duplicate_deliveries = 0
    for delivery in deliveries:
        result = cells[delivery.target_cell].receive(delivery.message)
        if result == "duplicate":
            duplicate_deliveries += 1

    # Explicitly test contract-version conflict and malformed payload rejection.
    conflict = ExperienceMessage("conflict-v2", 0, event_count + 1, 2, messages[-1].message_id, 1)
    malformed = ExperienceMessage("malformed", 0, event_count + 2, 1, None, 10_000)
    for cell in cells:
        cell.receive(conflict)
        cell.receive(malformed)

    reference_ids, reference_value = centralized_reference(messages)
    converged = all(set(cell.accepted) == reference_ids and cell.value == reference_value for cell in cells)
    pending_total = sum(len(cell.pending) for cell in cells)
    state_values = [cell.value for cell in cells]
    return {
        "cell_count": cell_count,
        "event_count": event_count,
        "seed": seed,
        "converged": converged,
        "reference_accepted": len(reference_ids),
        "min_accepted": min(len(cell.accepted) for cell in cells),
        "max_accepted": max(len(cell.accepted) for cell in cells),
        "state_divergence": max(state_values) - min(state_values),
        "reference_value": reference_value,
        "min_value": min(state_values),
        "max_value": max(state_values),
        "pending_messages": pending_total,
        "rejected_messages": sum(cell.rejected for cell in cells),
        "duplicate_deliveries": duplicate_deliveries,
        "bytes_sent": bytes_sent,
        "bytes_received": sum(cell.received_bytes for cell in cells),
        "convergence_tick": max((d.tick for d in deliveries), default=0),
        "partition": {"cell": cell_count - 1, "start": partition_start, "end": partition_end},
    }


def run_scale_sweep(cell_counts=(2, 4, 8, 16), event_count: int = 40, seed: int = 20261030) -> list[dict]:
    return [run_experiment(n, event_count, seed) for n in cell_counts]


def main() -> None:
    print(json.dumps(run_scale_sweep(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
