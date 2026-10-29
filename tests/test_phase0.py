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


class AdversarialPhase0Tests(unittest.TestCase):
    @staticmethod
    def reseal(events):
        from evo_geo import Archive
        bodies=[]
        for event in events:
            body=dict(event)
            body.pop("previous_hash",None)
            body.pop("event_hash",None)
            bodies.append(body)
        return Archive().prepare_bundle(bodies)

    def test_rehashed_checkpoint_tamper_rejected(self):
        from evo_geo.replay import replay_from_checkpoint
        e=Engine(contract=Contract(checkpoint_interval=1))
        e.step(zero(e.state))
        cp=dict(e.archive.checkpoints[1])
        cp["state"]=dict(cp["state"])
        cp["state"]["step"]=0
        cp["state_hash"]=__import__("evo_geo.core",fromlist=["sha256_hex"]).sha256_hex(canonical_bytes(cp["state"]))
        self.assertFalse((lambda a: a.verify())(self._archive_with(e.archive.events,cp,e.archive.contract)))
        with self.assertRaises(ValueError):
            replay_from_checkpoint(cp,e.archive.events,1)

    @staticmethod
    def _archive_with(events, checkpoint, contract=None):
        a=Archive(contract=contract); a.events=events; a.checkpoints={checkpoint["step"]:checkpoint}; return a

    def test_malformed_snapshot_rehashed_is_rejected(self):
        e=Engine()
        e.step(zero(e.state))
        bodies=[dict(x) for x in e.archive.events]
        commit=next(x for x in bodies if x.get("type")=="STEP_COMMITTED")
        commit["data"]["state"]["edges"]=[[999,1000]]
        a=Archive(); a.events=self.reseal(bodies)
        self.assertFalse(a.verify())

    def test_duplicate_commit_rehashed_is_rejected(self):
        e=Engine()
        e.step(zero(e.state))
        bodies=[dict(x) for x in e.archive.events]
        commit=dict(next(x for x in bodies if x.get("type")=="STEP_COMMITTED"))
        bodies.append(commit)
        a=Archive(); a.events=self.reseal(bodies)
        self.assertFalse(a.verify())

    def test_contract_rejects_invalid_numeric_bounds(self):
        with self.assertRaises(ValueError): Contract(R_Q=-1)
        with self.assertRaises(TypeError): Contract(Q=True)
        with self.assertRaises(ValueError): Contract(D_REMOVE_Q=1)

    def test_failed_bundle_preparation_is_transactional(self):
        e=Engine(contract=Contract(checkpoint_interval=1))
        before_state=state_to_dict(e.state)
        before_events=canonical_bytes(e.archive.events)
        before_checkpoints=dict(e.archive.checkpoints)
        def fail(_bundle):
            raise OSError("injected prepare failure")
        e.archive.prepare_bundle=fail
        with self.assertRaises(OSError):
            e.step(zero(e.state))
        self.assertEqual(state_to_dict(e.state),before_state)
        self.assertEqual(canonical_bytes(e.archive.events),before_events)
        self.assertEqual(e.archive.checkpoints,before_checkpoints)

    def test_state_parser_rejects_noncanonical_edge_and_duplicate_position(self):
        s=state_to_dict(initial_state())
        s["edges"]=[[2,1]]
        with self.assertRaises(ValueError): state_from_dict(s)
        s=state_to_dict(initial_state())
        s["vertices"][1]["x"]=s["vertices"][0]["x"]
        s["vertices"][1]["y"]=s["vertices"][0]["y"]
        with self.assertRaises(ValueError): state_from_dict(s)

    def test_rehashed_history_with_missing_committed_step_rejected(self):
        e=Engine()
        for _ in range(3):
            e.step(zero(e.state))
        bodies=[dict(x) for x in e.archive.events if x.get("step") != 2]
        a=Archive()
        a.events=self.reseal(bodies)
        self.assertFalse(a.verify())

    def test_archive_load_rejects_noncanonical_checkpoint_key(self):
        import json
        e=Engine(contract=Contract(checkpoint_interval=1))
        e.step(zero(e.state))
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"archive.json"
            e.archive.save_atomic(p)
            d=json.loads(p.read_text(encoding="utf-8"))
            d["checkpoints"]["01"]=d["checkpoints"].pop("1")
            p.write_text(json.dumps(d),encoding="utf-8")
            with self.assertRaises(ValueError):
                Archive.load(p)

    def test_archive_load_rejects_boolean_schema_version(self):
        import json
        e=Engine()
        e.step(zero(e.state))
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"archive.json"
            e.archive.save_atomic(p)
            d=json.loads(p.read_text(encoding="utf-8"))
            d["schema_version"]=True
            p.write_text(json.dumps(d),encoding="utf-8")
            with self.assertRaises(ValueError):
                Archive.load(p)


    def test_rehashed_move_event_semantic_tamper_rejected(self):
        e=Engine()
        e.step(zero(e.state))
        bodies=[dict(x) for x in e.archive.events]
        move=next(x for x in bodies if x.get("type")=="MOVE")
        move["data"]["x"] += 1
        a=Archive()
        a.events=self.reseal(bodies)
        self.assertFalse(a.verify())

        # The proposal is also semantically checked, not only the final x/y.
        bodies=[dict(x) for x in e.archive.events]
        move=next(x for x in bodies if x.get("type")=="MOVE")
        move["data"]["proposed_x"] += 1
        a=Archive()
        a.events=self.reseal(bodies)
        self.assertFalse(a.verify())

    def test_custom_contract_roundtrip_and_replay(self):
        from evo_geo.replay import replay_from_checkpoint
        c=Contract(R_MAX_Q=170000, max_coordinate_abs=200000, checkpoint_interval=1)
        e=Engine(contract=c)
        for _ in range(2):
            e.step(zero(e.state))
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"custom.json"
            e.archive.save_atomic(p)
            restored=Archive.load(p)
            self.assertEqual(restored.contract,c)
            recovered=replay_from_checkpoint(restored.checkpoints[1],restored.events,2)
            self.assertEqual(state_to_dict(recovered),state_to_dict(e.state))
        with self.assertRaises(ValueError):
            replay_from_checkpoint(e.archive.checkpoints[1],e.archive.events,2,contract=Contract())

    def test_storage_failures_preserve_previous_archive(self):
        from unittest.mock import patch
        import evo_geo.core as core
        e=Engine(contract=Contract(checkpoint_interval=1))
        e.step(zero(e.state))
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"archive.json"
            e.archive.save_atomic(p)
            original=Archive.load(p)
            e.step(zero(e.state))
            for failure_point in ("fsync","replace"):
                with self.subTest(failure_point=failure_point):
                    target=core.os.fsync if failure_point=="fsync" else core.os.replace
                    with patch("evo_geo.core.os."+failure_point, side_effect=OSError("injected storage failure")):
                        with self.assertRaises(OSError):
                            e.archive.save_atomic(p)
                    recovered=Archive.load(p)
                    self.assertEqual(len(recovered.events),len(original.events))
                    self.assertEqual(recovered.events,original.events)
                    self.assertEqual(recovered.checkpoints,original.checkpoints)
                    self.assertEqual([x for x in Path(td).iterdir() if x.name.endswith(".tmp")],[])

    def test_failure_after_replace_leaves_new_archive_verifiable(self):
        from unittest.mock import patch
        import evo_geo.core as core
        e=Engine(contract=Contract(checkpoint_interval=1))
        e.step(zero(e.state))
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"archive.json"
            e.archive.save_atomic(p)
            e.step(zero(e.state))
            real_replace=core.os.replace
            def replace_then_fail(src,dst):
                real_replace(src,dst)
                raise OSError("injected failure after rename")
            with patch("evo_geo.core.os.replace",side_effect=replace_then_fail):
                with self.assertRaises(OSError):
                    e.archive.save_atomic(p)
            recovered=Archive.load(p)
            self.assertEqual(recovered.events,e.archive.events)
            self.assertEqual(recovered.checkpoints,e.archive.checkpoints)

    @unittest.skipUnless(__import__("os").name=="posix","directory fsync is POSIX-specific")
    def test_directory_fsync_failure_reports_uncertain_durability_but_valid_new_archive(self):
        from unittest.mock import patch
        import evo_geo.core as core
        e=Engine(contract=Contract(checkpoint_interval=1))
        e.step(zero(e.state))
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"archive.json"
            e.archive.save_atomic(p)
            e.step(zero(e.state))
            real_fsync=core.os.fsync
            calls=0
            def fail_second_fsync(fd):
                nonlocal calls
                calls+=1
                if calls==2:
                    raise OSError("injected directory fsync failure")
                return real_fsync(fd)
            with patch("evo_geo.core.os.fsync",side_effect=fail_second_fsync):
                with self.assertRaises(OSError):
                    e.archive.save_atomic(p)
            recovered=Archive.load(p)
            self.assertEqual(recovered.events,e.archive.events)
            self.assertEqual(recovered.checkpoints,e.archive.checkpoints)

    def test_process_crash_before_replace_preserves_previous_archive(self):
        import subprocess, sys
        e=Engine(contract=Contract(checkpoint_interval=1))
        e.step(zero(e.state))
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"archive.json"
            e.archive.save_atomic(p)
            original=Archive.load(p)
            script = (
                "import os, sys; from evo_geo import Archive; "
                "import evo_geo.core as core; "
                "a=Archive.load(sys.argv[1]); "
                "core.os.replace=lambda *args, **kwargs: os._exit(77); "
                "a.save_atomic(sys.argv[1])"
            )
            result=subprocess.run([sys.executable,"-c",script,str(p)],check=False)
            self.assertEqual(result.returncode,77)
            recovered=Archive.load(p)
            self.assertEqual(recovered.events,original.events)
            self.assertEqual(recovered.checkpoints,original.checkpoints)
            # A hard process exit can leave an uncommitted temporary file.
            self.assertTrue(any(x.name.endswith(".tmp") for x in Path(td).iterdir()))

