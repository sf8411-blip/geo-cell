import unittest

from evo_geo.heldout_benchmark import (
    DOMAIN, candidate_rules, run_benchmark, run_trial, wilson_interval,
)


class HeldoutBenchmarkTests(unittest.TestCase):
    def test_candidate_grammar_is_nontrivial_and_deterministic(self):
        names = [rule.name for rule in candidate_rules()]
        self.assertGreaterEqual(len(names), 10)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(names, [rule.name for rule in candidate_rules()])

    def test_every_trial_keeps_training_and_heldout_sizes_explicit(self):
        row = run_trial(17, train_size=16)
        self.assertIn(row["split_mode"], {"random", "range_shift"})
        self.assertEqual(row, run_trial(17, train_size=16))
        self.assertGreaterEqual(row["majority_baseline_heldout_error"], 0.0)
        self.assertLessEqual(row["majority_baseline_heldout_error"], 1.0)
        self.assertGreaterEqual(row["random_candidate_heldout_error"], 0.0)
        self.assertLessEqual(row["random_candidate_heldout_error"], 1.0)
        self.assertEqual(row["train_size"], 16)
        self.assertEqual(row["heldout_size"], len(DOMAIN) - 16)
        self.assertGreaterEqual(row["heldout_error_clean_labels"], 0.0)
        self.assertLessEqual(row["heldout_error_clean_labels"], 1.0)

    def test_trial_is_reproducible(self):
        self.assertEqual(run_trial(123, 16, 0.25), run_trial(123, 16, 0.25))

    def test_adversarial_fraction_validation(self):
        with self.assertRaises(ValueError):
            run_trial(1, adversarial_fraction=-0.1)
        with self.assertRaises(ValueError):
            run_trial(1, adversarial_fraction=1.1)

    def test_train_size_validation(self):
        with self.assertRaises(ValueError):
            run_trial(1, train_size=3)
        with self.assertRaises(ValueError):
            run_trial(1, train_size=len(DOMAIN))

    def test_wilson_interval_contains_observed_rate(self):
        low, high = wilson_interval(3, 10)
        self.assertLessEqual(low, 0.3)
        self.assertGreaterEqual(high, 0.3)
        self.assertEqual(wilson_interval(0, 0), [0.0, 1.0])

    def test_benchmark_reports_uncertainty_and_attack_conditions(self):
        result = run_benchmark(trials=12, seed=77, attack_rates=(0.0, 0.25))
        self.assertEqual(result["trials_per_condition"], 12)
        self.assertEqual(len(result["conditions"]), 4)
        self.assertEqual({row["split_mode"] for row in result["conditions"]}, {"random", "range_shift"})
        for row in result["conditions"]:
            self.assertEqual(row["trials"], 12)
            self.assertIn("mean_majority_baseline_error", row)
            self.assertIn("mean_random_candidate_error", row)
            self.assertIn("win_rate_vs_majority", row)
            low, high = row["false_acceptance_95ci_wilson"]
            self.assertLessEqual(0.0, low)
            self.assertLessEqual(high, 1.0)
            self.assertLessEqual(low, high)
        self.assertIn("not open-ended rule invention", result["interpretation_limit"])

    def test_invalid_benchmark_trial_count(self):
        with self.assertRaises(ValueError):
            run_benchmark(trials=0)

    def test_range_shift_split_is_disjoint_and_covers_domain(self):
        row = run_trial(41, train_size=16, split_mode="range_shift")
        self.assertEqual(row["train_size"], 16)
        self.assertEqual(row["heldout_size"], len(DOMAIN) - 16)
        with self.assertRaises(ValueError):
            run_trial(41, split_mode="unknown")

    def test_benchmark_reports_all_attack_rates_for_each_split(self):
        result = run_benchmark(trials=3, attack_rates=(0.0, 0.5))
        keys = {(row["split_mode"], row["adversarial_fraction"]) for row in result["conditions"]}
        self.assertEqual(keys, {
            ("random", 0.0), ("random", 0.5),
            ("range_shift", 0.0), ("range_shift", 0.5),
        })


if __name__ == "__main__":
    unittest.main()
