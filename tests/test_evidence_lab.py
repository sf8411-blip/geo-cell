import unittest

from evo_geo.evidence_lab import (
    EvidenceCell, EvidenceMessage, Observation, build_scenario,
    run_evidence_experiment, run_scale_sweep,
)


class EvidenceLabTests(unittest.TestCase):
    def test_counterexample_retracts_false_acceptance(self):
        cell = EvidenceCell(0)
        proposal = EvidenceMessage("p", "proposal", 0, 1, "h", "constant_zero", None, ())
        evidence = EvidenceMessage(
            "e", "evidence", 0, 1, "h", "constant_zero", "p",
            (Observation(0, 0), Observation(2, 0), Observation(4, 0)),
        )
        counterexample = EvidenceMessage(
            "c", "counterexample", 1, 1, "h", "constant_zero", "e",
            (Observation(1, 1),),
        )
        self.assertEqual(cell.receive(proposal), "accepted")
        self.assertEqual(cell.receive(evidence), "accepted")
        self.assertEqual(cell.hypotheses["h"].status, "accepted")
        self.assertEqual(cell.receive(counterexample), "accepted")
        self.assertEqual(cell.hypotheses["h"].status, "rejected")
        self.assertEqual(cell.hypotheses["h"].retractions, 1)


    def test_conflicting_reports_cannot_overwrite_counterexample(self):
        cell = EvidenceCell(0)
        proposal = EvidenceMessage("p2", "proposal", 0, 1, "h2", "parity", None, ())
        good = EvidenceMessage(
            "e2", "evidence", 0, 1, "h2", "parity", "p2",
            (Observation(0, 0), Observation(2, 0), Observation(4, 0)),
        )
        contradictory = EvidenceMessage(
            "c2", "counterexample", 1, 1, "h2", "parity", "e2",
            (Observation(0, 1),),
        )
        cell.receive(proposal)
        cell.receive(good)
        self.assertEqual(cell.hypotheses["h2"].status, "accepted")
        cell.receive(contradictory)
        self.assertEqual(cell.hypotheses["h2"].status, "rejected")

    def test_unknown_hypothesis_evidence_is_buffered(self):
        cell = EvidenceCell(0)
        evidence = EvidenceMessage(
            "e", "evidence", 0, 1, "h", "parity", "p", (Observation(1, 1),)
        )
        self.assertEqual(cell.receive(evidence), "buffered")
        proposal = EvidenceMessage("p", "proposal", 0, 1, "h", "parity", None, ())
        cell.receive(proposal)
        self.assertIn("h", cell.hypotheses)
        self.assertEqual(cell.pending, {})
        self.assertEqual(cell.hypotheses["h"].status, "pending")

    def test_wrong_contract_and_bad_observation_rejected(self):
        cell = EvidenceCell(0)
        wrong_version = EvidenceMessage("v", "proposal", 0, 2, "h", "parity", None, ())
        malformed = EvidenceMessage(
            "m", "proposal", 0, 1, "bad", "parity", None, (Observation(2, 9),)
        )
        self.assertEqual(cell.receive(wrong_version), "invalid")
        self.assertEqual(cell.receive(malformed), "invalid")
        self.assertEqual(cell.rejected_messages, 2)

    def test_partition_rejoin_and_counterexamples_reduce_false_acceptance(self):
        result = run_evidence_experiment(cell_count=8, seed=99, partitioned_cell=7)
        before = result["initial"]
        after = result["after_counterexamples_and_rejoin"]
        self.assertTrue(result["recovery_complete"])
        self.assertEqual(result["pending_messages"], 0)
        self.assertGreater(before["accepted_false"], 0)
        self.assertLess(after["accepted_false"], before["accepted_false"])
        self.assertGreater(after["correct_rejections_of_false"], 0)
        self.assertGreater(after["retractions"], 0)

    def test_seeded_run_is_reproducible(self):
        self.assertEqual(run_evidence_experiment(4, 55, partitioned_cell=3),
                         run_evidence_experiment(4, 55, partitioned_cell=3))

    def test_scale_sweep(self):
        results = run_scale_sweep((2, 4, 8), seed=42)
        self.assertEqual([r["cell_count"] for r in results], [2, 4, 8])
        self.assertTrue(all(r["recovery_complete"] for r in results))
        self.assertTrue(all(r["after_counterexamples_and_rejoin"]["accepted_false"] <
                            r["initial"]["accepted_false"] for r in results))


if __name__ == "__main__":
    unittest.main()
