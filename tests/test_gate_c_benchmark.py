import unittest

from evo_geo.gate_c_benchmark import (
    TrialConfig, run_benchmark, run_trial, score_frozen_predictions,
)
from evo_geo.operator_discovery import Observation


class GateCBenchmarkTests(unittest.TestCase):
    def test_heldout_scorer_is_deterministic_and_does_not_mutate_predictions(self):
        rows = (Observation(9, 1), Observation(10, 0))
        predictions = (0, 0)
        before = tuple(predictions)
        result = score_frozen_predictions(rows, predictions)
        self.assertEqual(tuple(predictions), before)
        self.assertEqual(result["error_count"], 1)
        self.assertEqual(result["error_rate"], 0.5)
        self.assertEqual(result["counterexamples"], [
            {"x": 9, "expected": 1, "predicted": 0}
        ])

    def test_split_is_disjoint_and_budget_is_recorded(self):
        result = run_trial("parity", TrialConfig(seed=17, candidate_budget=500))
        self.assertEqual(result["split"]["overlap"], [])
        self.assertEqual(result["config"]["seed"], 17)
        self.assertEqual(result["config"]["candidate_budget"], 500)
        self.assertTrue(result["split"]["train_digest"])
        self.assertTrue(result["split"]["test_digest"])

    def test_heldout_failure_rejects_frozen_candidate_without_repair(self):
        result = run_trial("seeded_noise", TrialConfig(seed=3, candidate_budget=500))
        if result["frozen_candidate"]["expression"] is not None and result["heldout"]["error_count"]:
            self.assertEqual(result["disposition"], "rejected_by_heldout_counterexample")
            self.assertIsNotNone(result["counterexample_audit"])
            self.assertEqual(result["counterexample_audit"]["status"], "rejected")
        # Regardless of outcome, the selected candidate record is frozen and remains
        # identical to the record made before the held-out score.
        self.assertIn("candidate_id", result["frozen_candidate"])
        self.assertIn("expression", result["frozen_candidate"])


    def test_adversarial_heldout_shift_rejects_frozen_rule(self):
        result = run_trial("heldout_flip", TrialConfig(seed=5, candidate_budget=1000))
        self.assertEqual(result["frozen_candidate"]["expression"], "(x % 2)")
        self.assertEqual(result["heldout"]["error_rate"], 1.0)
        self.assertEqual(result["disposition"], "rejected_by_heldout_counterexample")
        self.assertEqual(result["counterexample_audit"]["status"], "rejected")
        self.assertEqual(result["counterexample_audit"]["contradictions"], result["heldout"]["counterexamples"])

    def test_benchmark_report_replays_byte_for_byte(self):
        config = TrialConfig(seed=11, candidate_budget=250)
        first = run_benchmark(config)
        second = run_benchmark(config)
        self.assertEqual(first, second)
        self.assertEqual(first["trial_count"], 5)
        self.assertTrue(first["report_digest"])

    def test_invalid_budgets_rejected(self):
        with self.assertRaises(ValueError):
            TrialConfig(candidate_budget=0)
        with self.assertRaises(ValueError):
            TrialConfig(max_cost=5)


if __name__ == "__main__":
    unittest.main()
