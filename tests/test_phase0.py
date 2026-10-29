import tempfile, unittest
from pathlib import Path
from evo_geo import Archive, Contract, Engine, ReplicationRequest, StepInputs, initial_state
from evo_geo.core import canonical_bytes, clip_to_radius, isqrt, round_even_div, state_from_dict, state_to_dict, verify_chain

def zero(s): return StepInputs({i:(0,0) for i in s.vertices},[])

class NumericTests(unittest.TestCase):
    def test_round_ties_even_signed(self):
        self.assertEqual([round_even_div(x,2) for x in (1,3,5,7,-1,-3,-5,-7)],[0,2,2,4,0,-2,-2,-4])
    def test_round_rejects_bool(self):
        with self.assertRaises(TypeError): round_even_div(True,2)
    def test_isqrt_bounds(self):
        for n in range(20000):
            r=isqrt(n); self.assertLessEqual(r*r,n); self.assertGreater((r+1)*(r+1),n)
    def test_clip_grid(self):
        for x in range(-30,31):
            for y in range(-30,31):
                nx,ny,_,_=clip_to_radius(x,y,17); self.assertLessEqual(nx*nx+ny*ny,289)
    def test_clip_zero_radius(self): self.assertEqual(clip_to_radius(3,-4,0),(0,0,True,1))

class EngineTests(unittest.TestCase):
    def test_initial_state(self):
        s=initial_state(); self.assertEqual(len(s.vertices),20)
        self.assertEqual({i for i,v in s.vertices.items() if v.special},{1,2,3,4})
    def test_serialization_roundtrip(self):
        s=initial_state(); self.assertEqual(state_to_dict(s),state_to_dict(state_from_dict(state_to_dict(s))))
    def test_deterministic_state_and_events(self):
        a,b=Engine(),Engine()
        for _ in range(5): a.step(zero(a.state)); b.step(zero(b.state))
        self.assertEqual(canonical_bytes(state_to_dict(a.state)),canonical_bytes(state_to_dict(b.state)))
        self.assertEqual(canonical_bytes(a.archive.events),canonical_bytes(b.archive.events))
    def test_bad_input_is_transactional(self):
        e=Engine(); before=state_to_dict(e.state); events=list(e.archive.events)
        with self.assertRaises(ValueError): e.step(StepInputs({},[]))
        self.assertEqual(state_to_dict(e.state),before); self.assertEqual(e.archive.events,events)
    def test_action_bound_and_type(self):
        e=Engine(); a={i:(0,0) for i in e.state.vertices}; a[1]=(e.contract.A_MAX_Q+1,0)
        with self.assertRaises(ValueError): e.step(StepInputs(a,[]))
        a[1]=(True,0)
        with self.assertRaises(ValueError): e.step(StepInputs(a,[]))
    def test_replication_and_monotonic_id(self):
        e=Engine(); req=ReplicationRequest("birth",1,170000,10000)
        out=e.step(StepInputs({i:(0,0) for i in e.state.vertices},[req]))
        self.assertIn(21,out.vertices); self.assertEqual(out.next_vertex_id,22)
    def test_request_conflict_does_not_mutate(self):
        e=Engine(); before=state_to_dict(e.state); count=len(e.archive.events)
        reqs=[ReplicationRequest("x",1,170000,10000),ReplicationRequest("x",2,180000,10000)]
        with self.assertRaises(ValueError): e.step(StepInputs({i:(0,0) for i in e.state.vertices},reqs))
        self.assertEqual(state_to_dict(e.state),before); self.assertEqual(len(e.archive.events),count)
    def test_hash_chain_checkpoint_and_tamper(self):
        e=Engine(contract=Contract(checkpoint_interval=1)); e.step(zero(e.state))
        self.assertTrue(e.archive.verify()); self.assertTrue(verify_chain(e.archive.events))
        e.archive.events[0]["type"]="tampered"; self.assertFalse(e.archive.verify())
    def test_atomic_archive_roundtrip(self):
        e=Engine(contract=Contract(checkpoint_interval=1)); e.step(zero(e.state))
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"archive.json"; e.archive.save_atomic(p); restored=Archive.load(p)
            self.assertEqual(canonical_bytes(restored.events),canonical_bytes(e.archive.events)); self.assertTrue(restored.verify())
    def test_archive_load_detects_tamper(self):
        e=Engine(); e.step(zero(e.state))
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"a.json"; e.archive.save_atomic(p); p.write_text(p.read_text().replace("STEP_STARTED","BAD"),encoding="utf-8")
            with self.assertRaises(ValueError): Archive.load(p)
    def test_50_step_invariants(self):
        e=Engine(contract=Contract(checkpoint_interval=5))
        for _ in range(50): e.step(zero(e.state)); e._validate(e.state)
        self.assertEqual(e.state.step,50); self.assertTrue(e.archive.verify())

if __name__=="__main__": unittest.main()

from evo_geo.replay import replay_from_checkpoint

class ReplayAndGraphTests(unittest.TestCase):
    def test_replay_from_checkpoint(self):
        e=Engine(contract=Contract(checkpoint_interval=1))
        for _ in range(4): e.step(zero(e.state))
        recovered=replay_from_checkpoint(e.archive.checkpoints[2],e.archive.events,4)
        self.assertEqual(state_to_dict(recovered),state_to_dict(e.state))

    def test_replay_rejects_corrupt_checkpoint(self):
        e=Engine(contract=Contract(checkpoint_interval=1)); e.step(zero(e.state))
        cp=dict(e.archive.checkpoints[1]); cp["state_hash"]="0"*64
        with self.assertRaises(ValueError): replay_from_checkpoint(cp,e.archive.events,1)

    def test_edge_hysteresis_boundaries(self):
        from evo_geo.core import State, Vertex
        c=Contract()
        # Absent edge at the add threshold is added.
        s=State(vertices={1:Vertex(1,0,0),2:Vertex(2,c.D_ADD_Q,0)},next_vertex_id=3)
        e=Engine(s,c); e._validate(e.state)
        e.step(StepInputs({1:(0,0),2:(0,0)},[]))
        self.assertIn((1,2),e.state.edges)
