"""Minimal multi-cell evidence provenance and conflict-preservation primitives.

This module deliberately does not implement Byzantine consensus or authenticated
identity. It provides deterministic content addressing, explicit provenance
metadata, and conflict-preserving aggregation for reproducible experiments.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class EvidenceReport:
    """A report with explicit lineage and an asserted independence group.

    The independence_group is metadata, not proof of independence. Production
    deployments need authenticated identities and externally auditable source
    attestations before treating it as trustworthy.
    """

    reporter_id: str
    source_id: str
    experiment_id: str
    claim_id: str
    value: Any
    independence_group: str
    parent_report_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "reporter_id", "source_id", "experiment_id", "claim_id",
            "independence_group",
        ):
            _nonempty(field_name, getattr(self, field_name))
        if not isinstance(self.parent_report_ids, tuple):
            raise ValueError("parent_report_ids must be a tuple")
        if any(not isinstance(item, str) or not item.strip() for item in self.parent_report_ids):
            raise ValueError("parent report IDs must be non-empty strings")
        if len(set(self.parent_report_ids)) != len(self.parent_report_ids):
            raise ValueError("parent report IDs must be unique")
        # Ensure value is JSON-serializable and stable under canonical encoding.
        try:
            _canonical_json(self.value)
        except (TypeError, ValueError) as exc:
            raise ValueError("value must be JSON-serializable") from exc

    def payload(self) -> dict[str, Any]:
        return {
            "reporter_id": self.reporter_id,
            "source_id": self.source_id,
            "experiment_id": self.experiment_id,
            "claim_id": self.claim_id,
            "value": self.value,
            "independence_group": self.independence_group,
            "parent_report_ids": list(self.parent_report_ids),
        }

    @property
    def report_id(self) -> str:
        """Deterministic content digest; integrity handle, not an identity signature."""
        return hashlib.sha256(_canonical_json(self.payload()).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ClaimAssessment:
    claim_id: str
    reports: tuple[EvidenceReport, ...]
    conflicting_values: tuple[Any, ...]
    independent_group_count: int
    source_count: int
    reporter_count: int
    duplicate_report_count: int

    @property
    def has_conflict(self) -> bool:
        return len(self.conflicting_values) > 1


def assess_claim(reports: Iterable[EvidenceReport], claim_id: str) -> ClaimAssessment:
    """Preserve all unique reports and count declared provenance groups.

    Reports with the same content digest are deduplicated. Different values are
    never majority-collapsed. JSON canonicalization is used for value equality.
    """
    _nonempty("claim_id", claim_id)
    unique: dict[str, EvidenceReport] = {}
    seen_count = 0
    for report in reports:
        if not isinstance(report, EvidenceReport):
            raise TypeError("reports must contain EvidenceReport objects")
        if report.claim_id != claim_id:
            continue
        seen_count += 1
        unique.setdefault(report.report_id, report)

    ordered = tuple(unique[key] for key in sorted(unique))
    values_by_key: dict[str, Any] = {}
    for report in ordered:
        values_by_key.setdefault(_canonical_json(report.value), report.value)
    groups = {report.independence_group for report in ordered}
    sources = {report.source_id for report in ordered}
    reporters = {report.reporter_id for report in ordered}
    return ClaimAssessment(
        claim_id=claim_id,
        reports=ordered,
        conflicting_values=tuple(values_by_key[key] for key in sorted(values_by_key)),
        independent_group_count=len(groups),
        source_count=len(sources),
        reporter_count=len(reporters),
        duplicate_report_count=seen_count - len(ordered),
    )
