import unittest

from evo_geo.network_lab import (
    Cell, ExperienceMessage, centralized_reference, make_chain, run_experiment, run_scale_sweep,
)


class NetworkProtocolLabTests(unittest.TestCase):
    def test_duplicate_delivery_is_idempotent(self):
        cell = Cell(0)
        message = make_chain(1, 7)[0]
        self.assertEqual(cell.receive(message), "accepted")
        value = cell.value
        self.assertEqual(cell.receive(message), "duplicate")
        self.assertEqual(cell.value, value)
        self.assertEqual(len(cell.accepted), 1)

    def test_out_of_order_message_waits_for_parent_then_drains(self):
        cell = Cell(0)
        first, second, third = make_chain(3, 8)
        self.assertEqual(cell.receive(third), "buffered")
        self.assertEqual(cell.receive(second), "buffered")
        self.assertEqual(cell.receive(first), "accepted")
        self.assertEqual(set(cell.accepted), {first.message_id, second.message_id, third.message_id})
        self.assertEqual(cell.pending, {})

    def test_contract_conflict_and_malformed_experience_rejected(self):
        cell = Cell(0)
        conflict = ExperienceMessage("v2", 0, 1, 2, None, 1)
        malformed = ExperienceMessage("bad", 0, 1, 1, None, 1000)
        self.assertEqual(cell.receive(conflict), "version_conflict")
        self.assertEqual(cell.receive(malformed), "invalid")
        self.assertEqual(cell.accepted, {})
        self.assertEqual(cell.rejected, 2)

    def test_centralized_reference(self):
        messages = make_chain(20, 123)
        ids, value = centralized_reference(messages)
        self.assertEqual(len(ids), 20)
        self.assertEqual(value, sum(m.delta for m in messages))

    def test_partition_rejoin_duplicates_and_reference_convergence(self):
        result = run_experiment(cell_count=8, event_count=40, seed=91, partition_start=8, partition_end=13)
        self.assertTrue(result["converged"], result)
        self.assertEqual(result["state_divergence"], 0)
        self.assertEqual(result["pending_messages"], 0)
        self.assertGreater(result["duplicate_deliveries"], 0)
        self.assertGreater(result["rejected_messages"], 0)
        self.assertGreater(result["bytes_sent"], 0)
        self.assertGreaterEqual(result["bytes_received"], result["bytes_sent"])

    def test_seeded_experiment_is_reproducible(self):
        self.assertEqual(run_experiment(4, 12, 77), run_experiment(4, 12, 77))

    def test_scale_sweep_reports_each_requested_scale(self):
        results = run_scale_sweep((2, 4, 8), event_count=12, seed=55)
        self.assertEqual([r["cell_count"] for r in results], [2, 4, 8])
        self.assertTrue(all(r["converged"] for r in results))
        self.assertTrue(all(r["state_divergence"] == 0 for r in results))


if __name__ == "__main__":
    unittest.main()
