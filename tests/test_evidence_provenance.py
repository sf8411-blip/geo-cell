import unittest

from evo_geo.evidence_provenance import EvidenceReport, assess_claim


def report(reporter, value, *, source="sensor-A", group="lineage-A", parents=()):
    return EvidenceReport(
        reporter_id=reporter,
        source_id=source,
        experiment_id="exp-001",
        claim_id="claim-temperature",
        value=value,
        independence_group=group,
        parent_report_ids=parents,
    )


class EvidenceProvenanceTests(unittest.TestCase):
    def test_report_id_is_deterministic_and_sensitive_to_payload(self):
        a = report("cell-1", {"result": 7})
        b = report("cell-1", {"result": 7})
        c = report("cell-2", {"result": 7})
        self.assertEqual(a.report_id, b.report_id)
        self.assertNotEqual(a.report_id, c.report_id)
        self.assertEqual(len(a.report_id), 64)

    def test_conflicting_reports_are_preserved_not_majority_collapsed(self):
        reports = [
            report("cell-1", "positive"),
            report("cell-2", "positive"),
            report("cell-3", "negative", source="sensor-B", group="lineage-B"),
        ]
        assessment = assess_claim(reports, "claim-temperature")
        self.assertTrue(assessment.has_conflict)
        self.assertEqual(set(assessment.conflicting_values), {"positive", "negative"})
        self.assertEqual(len(assessment.reports), 3)

    def test_same_lineage_does_not_count_as_multiple_independent_groups(self):
        reports = [
            report("cell-1", 1, source="shared-feed", group="shared-origin"),
            report("cell-2", 1, source="shared-feed", group="shared-origin"),
            report("cell-3", 1, source="shared-feed", group="shared-origin"),
        ]
        assessment = assess_claim(reports, "claim-temperature")
        self.assertEqual(assessment.reporter_count, 3)
        self.assertEqual(assessment.independent_group_count, 1)
        self.assertEqual(assessment.source_count, 1)

    def test_identical_duplicate_report_is_deduplicated_and_counted(self):
        item = report("cell-1", 1)
        assessment = assess_claim([item, item, item], "claim-temperature")
        self.assertEqual(len(assessment.reports), 1)
        self.assertEqual(assessment.duplicate_report_count, 2)

    def test_different_claims_are_ignored(self):
        wanted = report("cell-1", 1)
        other = EvidenceReport(
            reporter_id="cell-2", source_id="sensor-B", experiment_id="exp-002",
            claim_id="another-claim", value=0, independence_group="lineage-B",
        )
        assessment = assess_claim([wanted, other], "claim-temperature")
        self.assertEqual(len(assessment.reports), 1)
        self.assertEqual(assessment.conflicting_values, (1,))

    def test_invalid_empty_metadata_is_rejected(self):
        with self.assertRaises(ValueError):
            report("", 1)

    def test_parent_ids_must_be_unique(self):
        with self.assertRaises(ValueError):
            report("cell-1", 1, parents=("abc", "abc"))

    def test_non_json_values_are_rejected(self):
        with self.assertRaises(ValueError):
            report("cell-1", object())


if __name__ == "__main__":
    unittest.main()
