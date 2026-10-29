"""Heuristic audit signals for adversarial multi-cell evidence scenarios.

These checks expose suspicious metadata concentration; they do not authenticate
identities, prove collusion, or establish source independence.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .evidence_provenance import EvidenceReport, assess_claim


@dataclass(frozen=True)
class ProvenanceRiskAudit:
    claim_id: str
    report_count: int
    reporter_count: int
    source_count: int
    declared_group_count: int
    max_reports_per_source: int
    max_reports_per_group: int
    max_reports_sharing_parent: int
    flags: tuple[str, ...]


def audit_claim_provenance(
    reports: Iterable[EvidenceReport], claim_id: str
) -> ProvenanceRiskAudit:
    """Summarize metadata risk signals for one claim without voting on its value.

    A flag is a reason for further investigation, not a security verdict.
    Report identity and independence metadata are self-asserted in this phase.
    """
    assessment = assess_claim(reports, claim_id)
    selected = assessment.reports
    source_counts = Counter(item.source_id for item in selected)
    group_counts = Counter(item.independence_group for item in selected)
    parent_counts = Counter(
        parent_id for item in selected for parent_id in item.parent_report_ids
    )
    max_source = max(source_counts.values(), default=0)
    max_group = max(group_counts.values(), default=0)
    max_parent = max(parent_counts.values(), default=0)
    flags: list[str] = []

    if len(selected) > 1 and max_source > 1:
        flags.append("shared_source_concentration")
    if len(selected) > 1 and max_group > 1:
        flags.append("shared_declared_lineage")
    if assessment.reporter_count > assessment.source_count:
        flags.append("reporter_to_source_fanout")
    if assessment.independent_group_count > assessment.source_count:
        flags.append("more_declared_groups_than_sources")
    if max_parent > 1:
        flags.append("shared_parent_lineage")
    if assessment.has_conflict:
        flags.append("conflicting_values_preserved")

    return ProvenanceRiskAudit(
        claim_id=claim_id,
        report_count=len(selected),
        reporter_count=assessment.reporter_count,
        source_count=assessment.source_count,
        declared_group_count=assessment.independent_group_count,
        max_reports_per_source=max_source,
        max_reports_per_group=max_group,
        max_reports_sharing_parent=max_parent,
        flags=tuple(flags),
    )
