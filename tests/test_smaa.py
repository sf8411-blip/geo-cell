import unittest
from smaa import IsolatedCellProcess, SMAAEngine, Capability, KnowledgeClaim, Prediction, EventLedger, brier_score, expected_calibration_error, run_reference_suite
class SMAATests(unittest.TestCase):
 def test_eight_reference_probes(self):
  r=run_reference_suite(); self.assertTrue(all(r["tests"].values()),r["tests"]); self.assertTrue(r["audit"]["ledger_valid"])
 def test_private_evidence_rejected(self):
  e=SMAAEngine("n"); e.register_cell("c")
  with self.assertRaises(ValueError): e.receive_public_summary("c",{"local_evidence":[1]})
 def test_unknown_fields_rejected(self):
  e=SMAAEngine("n"); e.register_cell("c")
  with self.assertRaises(ValueError): e.receive_public_summary("c",{"secret":"x"})
 def test_allowlisted_summary(self):
  e=SMAAEngine("n"); e.register_cell("c"); e.receive_public_summary("c",{"resource_cpu":.5,"reported_unknowns":["x"]})
  self.assertEqual(e.model.resources["c.resource_cpu"],.5); self.assertIn("x",e.model.unknowns)
 def test_ledger_tamper_detection(self):
  l=EventLedger(); l.append("x","a",0,{"v":1}); self.assertTrue(l.verify()); l.events[0].payload["v"]=2; self.assertFalse(l.verify())
 def test_duplicate_prediction(self):
  e=SMAAEngine("n"); p=Prediction("p","x",.5); e.record_prediction(p)
  with self.assertRaises(ValueError): e.record_prediction(p)
 def test_calibration(self):
  self.assertAlmostEqual(brier_score([.8,.2],[1,0]),.04); self.assertGreaterEqual(expected_calibration_error([.8,.2],[1,0]),0)
 def test_revision_requires_reason(self):
  with self.assertRaises(ValueError): SMAAEngine("n").revise_self_model("",[])
 def test_capability_bounds(self):
  with self.assertRaises(ValueError): Capability("x",1.2,3)
 def test_knowledge_owner_required(self):
  with self.assertRaises(ValueError): SMAAEngine("n").add_knowledge_claim(KnowledgeClaim("k","p","missing"),"missing")

 def test_self_model_changes_action_selection(self):
  e=SMAAEngine("n")
  self.assertEqual(e.choose_action("geometry"),"abstain")
  e.add_capability(Capability("geometry",.9,20,("blind-test-1",)))
  self.assertEqual(e.choose_action("geometry"),"attempt")
  e.model.capabilities.pop("geometry")
  self.assertEqual(e.choose_action("geometry"),"abstain")
 def test_isolated_cell_only_exports_allowlisted_summary(self):
  with IsolatedCellProcess("cell-private",["geometry"]) as cell:
   cell.observe({"raw_observation":"secret-data","hidden_label":17})
   cell.report_unknown("unseen-shape")
   summary=cell.public_summary()
   self.assertEqual(summary["cell_id"],"cell-private")
   self.assertEqual(summary["capability_names"],["geometry"])
   self.assertEqual(summary["reported_unknowns"],["unseen-shape"])
   self.assertNotIn("raw_observation",summary)
   self.assertNotIn("hidden_label",summary)
\nif __name__=="__main__": unittest.main()
