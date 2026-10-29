import unittest
from evo_geo.operator_discovery import (GRAMMAR_VERSION, Observation, check_counterexamples,
    enumerate_candidates, evaluate, search)

class OperatorDiscoveryTests(unittest.TestCase):
    def test_deterministic_bounded_canonical_enumeration(self):
        a=enumerate_candidates(4,250); b=enumerate_candidates(4,250)
        self.assertEqual([e.canonical() for e in a],[e.canonical() for e in b])
        self.assertLessEqual(len(a),250)
        self.assertEqual(len({e.canonical() for e in a}),len(a))
        self.assertTrue(all(e.cost<=4 for e in a))
    def test_discovers_expression_relative_to_initial_list(self):
        obs=[Observation(x,x%2) for x in range(8)]
        a=search(obs,max_cost=4,max_candidates=1000)
        self.assertEqual(a.status,"candidate_found")
        self.assertNotIn(a.selected,{"x","0","1"})
        self.assertEqual(a.training_error,0.0)
        self.assertEqual(a.grammar_version,GRAMMAR_VERSION)
        self.assertEqual(a,search(obs,max_cost=4,max_candidates=1000))
    def test_candidate_evaluation(self):
        expr=next(e for e in enumerate_candidates(4,1000) if e.canonical()=="(x % 2)")
        self.assertEqual([evaluate(expr,x) for x in range(8)],[x%2 for x in range(8)])
    def test_conflicts_force_abstention(self):
        r=search([Observation(2,0),Observation(2,1),Observation(4,0),Observation(6,0)])
        self.assertEqual(r.status,"insufficient_evidence")
        self.assertEqual(r.log[0]["reason"],"contradictory_observations")
    def test_sparse_data_force_abstention(self):
        r=search([Observation(0,0),Observation(1,1),Observation(2,0)])
        self.assertEqual(r.status,"insufficient_evidence")
    def test_counterexample_rejects_candidate(self):
        r=check_counterexamples("(x % 2)",[Observation(2,1)])
        self.assertEqual(r["status"],"rejected")
        self.assertEqual(r["contradictions"],[{"x":2,"y":1,"prediction":0}])
    def test_invalid_observations_and_budgets(self):
        for x,y in [(True,1),(17,1),(0,True),(0,2)]:
            with self.assertRaises(ValueError): Observation(x,y)
        with self.assertRaises(ValueError): enumerate_candidates(0,10)
        with self.assertRaises(ValueError): enumerate_candidates(5,10)
        with self.assertRaises(ValueError): enumerate_candidates(2,0)
    def test_nonbinary_candidate_output_rejected(self):
        expr=next(e for e in enumerate_candidates(3,1000) if e.canonical()=="(x + 1)")
        with self.assertRaises(ValueError): evaluate(expr,1)

if __name__=="__main__": unittest.main()
