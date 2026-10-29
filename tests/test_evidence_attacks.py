import unittest

from evo_geo.evidence_attacks import audit_claim_provenance
from evo_geo.evidence_provenance import EvidenceReport


def report(reporter, value, *, source, group, parents=(), claim="claim-1"):
    return EvidenceReport(
        reporter_id=reporter,
        source_id=source,
        experiment_id="experiment-1",
        claim_id=claim,
        value=value,
        independence_group=group,
        parent_report_ids=parents,
    )


class AdversarialProvenanceScenarioTests(unittest.TestCase):
    def test_coordinated_reporters_using_one_source_are_flagged(self):
        reports = [
            report("cell-a", "yes", source="sensor-1", group="lineage-1"),
            report("cell-b", "yes", source="sensor-1", group="lineage-1"),
            report("cell-c", "yes", source="sensor-1", group="lineage-1"),
        ]
        audit = audit_claim_provenance(reports, "claim-1")
        self.assertEqual(audit.reporter_count, 3)
        self.assertEqual(audit.source_count, 1)
        self.assertIn("shared_source_concentration", audit.flags)
        self.assertIn("shared_declared_lineage", audit.flags)
        self.assertIn("reporter_to_source_fanout", audit.flags)

    def test_many_reporter_ids_do_not_count_as_many_sources(self):
        reports = [
            report(f"cell-{i}", "yes", source="one-feed", group=f"claimed-{i}")
            for i in range(12)
        ]
        audit = audit_claim_provenance(reports, "claim-1")
        self.assertEqual(audit.reporter_count, 12)
        self.assertEqual(audit.source_count, 1)
        self.assertEqual(audit.declared_group_count, 12)
        self.assertIn("reporter_to_source_fanout", audit.flags)
        self.assertIn("more_declared_groups_than_sources", audit.flags)

    def test_shared_parent_lineage_is_flagged(self):
        reports = [
            report("cell-a", "yes", source="sensor-a", group="lineage-a",
                   parents=("root-report",)),
            report("cell-b", "yes", source="sensor-b", group="lineage-b",
                   parents=("root-report",)),
        ]
        audit = audit_claim_provenance(reports, "claim-1")
        self.assertEqual(audit.max_reports_sharing_parent, 2)
        self.assertIn("shared_parent_lineage", audit.flags)

    def test_conflicting_values_are_preserved_and_flagged(self):
        reports = [
            report("cell-a", "yes", source="sensor-a", group="lineage-a"),
            report("cell-b", "no", source="sensor-b", group="lineage-b"),
            report("cell-c", "no", source="sensor-c", group="lineage-c"),
        ]
        audit = audit_claim_provenance(reports, "claim-1")
        self.assertIn("conflicting_values_preserved", audit.flags)
        self.assertEqual(audit.report_count, 3)

    def test_unrelated_claims_do_not_inflate_audit(self):
        reports = [
            report("cell-a", "yes", source="sensor-a", group="lineage-a"),
            report("cell-b", "yes", source="sensor-a", group="lineage-a",
                   claim="claim-2"),
        ]
        audit = audit_claim_provenance(reports, "claim-1")
        self.assertEqual(audit.report_count, 1)
        self.assertEqual(audit.reporter_count, 1)
        self.assertEqual(audit.flags, ())

    def test_empty_claim_has_zero_counts_and_no_flags(self):
        audit = audit_claim_provenance([], "claim-1")
        self.assertEqual(audit.report_count, 0)
        self.assertEqual(audit.flags, ())


if __name__ == "__main__":
    unittest.main()
