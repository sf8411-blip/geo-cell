"""Phase 0 deterministic integer-lattice engine; no runtime dependencies."""
from __future__ import annotations
import hashlib, json, os, tempfile, contextlib
from dataclasses import dataclass, field
from pathlib import Path

@contextlib.contextmanager
def _exclusive_path_lock(lock_path):
    """Advisory process lock; lock file is persistent and must not be deleted by callers."""
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+b") as lock_file:
        if os.name == "nt":
            import msvcrt
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\\0"); lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

def canonical_bytes(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def sha256_hex(data): return hashlib.sha256(data).hexdigest()

def round_even_div(a: int, b: int) -> int:
    if type(a) is not int or type(b) is not int: raise TypeError("integer operands required; bool is not accepted")
    if b <= 0: raise ValueError("denominator must be positive")
    sign = -1 if a < 0 else 1
    q, r = divmod(abs(a), b)
    if 2*r > b or (2*r == b and q % 2): q += 1
    return sign*q

def isqrt(n: int) -> int:
    if type(n) is not int: raise TypeError("integer input required")
    if n < 0: raise ValueError("n must be nonnegative")
    if n < 2: return n
    x = 1 << ((n.bit_length()+1)//2)
    while True:
        y = (x+n//x)//2
        if y >= x: return x
        x = y

@dataclass(frozen=True)
class Contract:
    spec_version: str = "evo-geo-phase-0.4"
    Q: int = 65536
    R_Q: int = 163840
    R_MAX_Q: int = 229376
    H_Q: int = 52429
    D_ADD_Q: int = 58982
    D_REMOVE_Q: int = 72090
    A_MAX_Q: int = 3277
    checkpoint_interval: int = 10
    max_coordinate_abs: int = 10**9
    def __post_init__(self):
        if not isinstance(self.spec_version,str) or not self.spec_version:
            raise ValueError("spec_version must be a non-empty string")
        integer_fields=("Q","R_Q","R_MAX_Q","H_Q","D_ADD_Q","D_REMOVE_Q","A_MAX_Q","checkpoint_interval","max_coordinate_abs")
        if any(type(getattr(self,k)) is not int for k in integer_fields):
            raise TypeError("contract numeric fields must be integers; bool is not accepted")
        if self.Q<=0 or self.R_Q<=0 or self.R_MAX_Q<self.R_Q or self.H_Q<=0 or self.D_ADD_Q<=0 or self.D_REMOVE_Q<=self.D_ADD_Q or self.A_MAX_Q<0 or self.checkpoint_interval<0 or self.max_coordinate_abs<=0:
            raise ValueError("invalid contract bounds")
    @property
    def r2(self): return self.R_Q**2
    @property
    def rmax2(self): return self.R_MAX_Q**2
    @property
    def add2(self): return self.D_ADD_Q**2
    @property
    def remove2(self): return self.D_REMOVE_Q**2
    @property
    def h2_twice(self): return 2*self.H_Q**2

@dataclass
class Vertex:
    id: int
    x: int
    y: int
    special: bool = False

@dataclass
class State:
    step: int = 0
    vertices: dict[int, Vertex] = field(default_factory=dict)
    edges: set[tuple[int,int]] = field(default_factory=set)
    next_vertex_id: int = 1
    processed_requests: dict[str,dict] = field(default_factory=dict)
    def clone(self):
        return State(self.step,{i:Vertex(v.id,v.x,v.y,v.special) for i,v in self.vertices.items()},set(self.edges),self.next_vertex_id,{k:dict(v) for k,v in self.processed_requests.items()})

@dataclass(frozen=True)
class ReplicationRequest:
    request_id: str
    parent_id: int
    child_x: int
    child_y: int
    def payload(self): return {"parent_id":self.parent_id,"child_x":self.child_x,"child_y":self.child_y}

@dataclass
class StepInputs:
    direct_actions: dict[int,tuple[int,int]] = field(default_factory=dict)
    replication_requests: list[ReplicationRequest] = field(default_factory=list)

_INITIAL = ((163840,0),(155821,50629),(132549,96303),(96303,132549),(50629,155821),(0,163840),(-50629,155821),(-96303,132549),(-132549,96303),(-155821,50629),(-163840,0),(-155821,-50629),(-132549,-96303),(-96303,-132549),(-50629,-155821),(0,-163840),(50629,-155821),(96303,-132549),(132549,-96303),(155821,-50629))

def initial_state():
    s=State()
    for i,(x,y) in enumerate(_INITIAL,1): s.vertices[i]=Vertex(i,x,y,i<=len(_INITIAL)//5)
    s.next_vertex_id=len(_INITIAL)+1
    return s

def state_to_dict(s):
    return {"step":s.step,"vertices":[{"id":v.id,"x":v.x,"y":v.y,"special":v.special} for _,v in sorted(s.vertices.items())],"edges":[list(e) for e in sorted(s.edges)],"next_vertex_id":s.next_vertex_id,"processed_requests":{k:s.processed_requests[k] for k in sorted(s.processed_requests)}}

def state_from_dict(d):
    required={"step","vertices","edges","next_vertex_id","processed_requests"}
    if not isinstance(d,dict) or set(d)!=required:
        raise ValueError("invalid state schema")
    if type(d["step"]) is not int or d["step"]<0 or type(d["next_vertex_id"]) is not int:
        raise ValueError("invalid state counters")
    if not isinstance(d["vertices"],list) or not isinstance(d["edges"],list) or not isinstance(d["processed_requests"],dict):
        raise ValueError("invalid state collections")
    vertices={}
    positions=set()
    for row in d["vertices"]:
        if not isinstance(row,dict) or set(row)!={"id","x","y","special"} or any(type(row[k]) is not int for k in ("id","x","y")) or type(row["special"]) is not bool:
            raise ValueError("invalid vertex")
        if row["id"]<=0 or row["id"] in vertices or (row["x"],row["y"]) in positions:
            raise ValueError("duplicate or invalid vertex identity/position")
        vertices[row["id"]]=Vertex(row["id"],row["x"],row["y"],row["special"])
        positions.add((row["x"],row["y"]))
    if d["next_vertex_id"]<=max(vertices,default=0):
        raise ValueError("non-monotonic next vertex ID")
    if {i for i,v in vertices.items() if v.special} != special_ids(vertices):
        raise ValueError("special status inconsistent")
    edges=set()
    for row in d["edges"]:
        if not isinstance(row,list) or len(row)!=2 or any(type(x) is not int for x in row):
            raise ValueError("invalid edge")
        a,b=row
        if a>=b or a not in vertices or b not in vertices or (a,b) in edges:
            raise ValueError("non-canonical, dangling, or duplicate edge")
        edges.add((a,b))
    pr=d["processed_requests"]
    for rid,result in pr.items():
        if not isinstance(rid,str) or not rid or not isinstance(result,dict):
            raise ValueError("invalid processed request")
        if result.get("status") not in ("accepted","rejected") or not isinstance(result.get("payload"),dict):
            raise ValueError("invalid processed request result")
        payload=result["payload"]
        if set(payload)!={"parent_id","child_x","child_y"} or any(type(payload[k]) is not int for k in payload):
            raise ValueError("invalid processed request payload")
        if result["status"]=="accepted":
            if set(result)!={"status","child_id","payload"} or type(result["child_id"]) is not int or result["child_id"] not in vertices:
                raise ValueError("invalid accepted request result")
        elif set(result)!={"status","reason","payload"} or not isinstance(result["reason"],str) or not result["reason"]:
            raise ValueError("invalid rejected request result")
    return State(d["step"],vertices,edges,d["next_vertex_id"],{k:dict(v) for k,v in pr.items()})

def dist2(a,b): return (a.x-b.x)**2+(a.y-b.y)**2
def special_ids(vertices): return set(sorted(vertices)[:len(vertices)//5])

def clip_to_radius(x,y,radius):
    if any(type(v) is not int for v in (x,y,radius)): raise TypeError("integer arguments required")
    if radius<0: raise ValueError("radius must be nonnegative")
    if x*x+y*y<=radius*radius: return x,y,False,0
    if radius==0: return 0,0,True,int(x!=0 or y!=0)
    n=isqrt(x*x+y*y); nx=round_even_div(radius*x,n); ny=round_even_div(radius*y,n); corrections=0
    while nx*nx+ny*ny>radius*radius:
        if abs(nx)>=abs(ny): nx-=1 if nx>0 else -1
        else: ny-=1 if ny>0 else -1
        corrections+=1
        if corrections>8: raise ArithmeticError("radial clipping safety bound exceeded")
    return nx,ny,True,corrections

def contract_to_dict(c):
    return {k:getattr(c,k) for k in ("spec_version","Q","R_Q","R_MAX_Q","H_Q","D_ADD_Q","D_REMOVE_Q","A_MAX_Q","checkpoint_interval","max_coordinate_abs")}

def contract_from_dict(d):
    required={"spec_version","Q","R_Q","R_MAX_Q","H_Q","D_ADD_Q","D_REMOVE_Q","A_MAX_Q","checkpoint_interval","max_coordinate_abs"}
    if not isinstance(d,dict) or set(d)!=required:
        raise ValueError("invalid contract schema")
    return Contract(**d)

class Archive:
    def __init__(self, contract=None):
        self.contract=contract or Contract()
        self.events=[]
        self.checkpoints={}
    def prepare_bundle(self,bundle):
        previous=self.events[-1]["event_hash"] if self.events else "0"*64
        sealed=[]
        for event in bundle:
            item=dict(event); item["previous_hash"]=previous; item["event_hash"]=sha256_hex(canonical_bytes(item)); sealed.append(item); previous=item["event_hash"]
        return sealed
    def commit_bundle(self,sealed): self.events.extend(dict(e) for e in sealed)
    def append_bundle(self,bundle):
        sealed=self.prepare_bundle(bundle); self.commit_bundle(sealed); return sealed
    def checkpoint(self,state):
        payload=state_to_dict(state); cp={"step":state.step,"state":payload,"state_hash":sha256_hex(canonical_bytes(payload))}; self.checkpoints[state.step]=cp; return cp
    def verify_genesis_anchor(self, expected_sha256):
        """Verify the first recorded start-state against an externally trusted SHA-256 anchor.

        The expected digest must arrive through a separately trusted channel. This method
        binds the archive to that digest; it does not itself establish who created the anchor.
        """
        if (not isinstance(expected_sha256, str) or len(expected_sha256) != 64
                or any(ch not in "0123456789abcdef" for ch in expected_sha256)):
            return False
        if not self.verify() or not self.events:
            return False
        first = next((e for e in self.events if e.get("type") == "STEP_STARTED"), None)
        if first is None:
            return False
        try:
            genesis = first["data"]["start_state"]
            state_from_dict(genesis)
            actual = sha256_hex(canonical_bytes(genesis))
        except (KeyError, TypeError, ValueError):
            return False
        return actual == expected_sha256

    def verify(self):
        if (not isinstance(self.contract, Contract) or not isinstance(self.checkpoints, dict)
                or not verify_chain(self.events)):
            return False
        previous_step=0
        snapshots={}
        start_snapshots={}
        action_snapshots={}
        by_step={}
        allowed={
            "STEP_STARTED": (0, {"from_step","contract","start_state","actions"}),
            "MOVE": (1, {"x","y","proposed_x","proposed_y"}),
            "BOUNDARY_CLIP": (2, {"x","y","corrections"}),
            "REPLICATION_REPLAY": (3, {"request_id","payload"}),
            "REPLICATION_REJECT": (3, {"request_id","status","reason","payload"}),
            "REPLICATION_ACCEPT": (3, {"request_id","status","child_id","payload"}),
            "SPECIAL_STATUS_CHANGE": (4, {"special"}),
            "EDGE_ADD": (5, set()),
            "EDGE_REMOVE": (5, set()),
            "STEP_COMMITTED": (8, {"state"}),
        }
        for e in self.events:
            if not isinstance(e,dict) or set(e) not in (
                {"step","phase","type","data","previous_hash","event_hash"},
                {"step","phase","type","entity_ids","data","previous_hash","event_hash"},
            ):
                return False
            step,phase,kind=e.get("step"),e.get("phase"),e.get("type")
            if type(step) is not int or step<=0 or type(phase) is not int or type(kind) is not str or kind not in allowed:
                return False
            expected_phase,keys=allowed[kind]
            if phase!=expected_phase or not isinstance(e.get("data"),dict) or set(e["data"])!=keys:
                return False
            has_ids="entity_ids" in e
            if has_ids:
                ids=e["entity_ids"]
                if not isinstance(ids,list) or not ids or any(type(i) is not int or i<=0 for i in ids) or len(set(ids))!=len(ids):
                    return False
            if kind in ("STEP_STARTED","REPLICATION_REPLAY","REPLICATION_REJECT","STEP_COMMITTED") and has_ids:
                return False
            if kind in ("MOVE","BOUNDARY_CLIP","SPECIAL_STATUS_CHANGE","EDGE_ADD","EDGE_REMOVE","REPLICATION_ACCEPT") and not has_ids:
                return False
            if kind=="STEP_STARTED":
                if step!=previous_step+1 or e["data"]["from_step"]!=previous_step or type(e["data"]["from_step"]) is not int:
                    return False
                try:
                    if contract_from_dict(e["data"]["contract"]) != self.contract:
                        return False
                    start_state=state_from_dict(e["data"]["start_state"])
                    Engine(state=start_state,contract=self.contract)
                except (TypeError,ValueError,KeyError):
                    return False
                if start_state.step != e["data"]["from_step"]:
                    return False
                actions=e["data"]["actions"]
                if not isinstance(actions,dict) or set(actions)!={str(i) for i in start_state.vertices}:
                    return False
                parsed_actions={}
                for key,value in actions.items():
                    if not isinstance(key,str) or not key.isdecimal() or str(int(key))!=key or not isinstance(value,list) or len(value)!=2 or any(type(z) is not int for z in value):
                        return False
                    parsed_actions[int(key)]=(value[0],value[1])
                    if any(abs(z)>self.contract.A_MAX_Q for z in value):
                        return False
                if step>1 and state_to_dict(start_state)!=snapshots.get(step-1):
                    return False
                start_snapshots[step]=state_to_dict(start_state)
                action_snapshots[step]=parsed_actions
                by_step[step]=[]
            elif step not in by_step:
                return False
            if by_step.get(step) is not None:
                by_step[step].append(e)
            if kind=="MOVE":
                if len(e["entity_ids"])!=1 or any(type(e["data"][k]) is not int for k in keys):
                    return False
            elif kind=="BOUNDARY_CLIP":
                if len(e["entity_ids"])!=1 or any(type(e["data"][k]) is not int for k in ("x","y","corrections")) or e["data"]["corrections"]<0:
                    return False
            elif kind=="SPECIAL_STATUS_CHANGE":
                if len(e["entity_ids"])!=1 or type(e["data"]["special"]) is not bool:
                    return False
            elif kind in ("EDGE_ADD","EDGE_REMOVE"):
                if len(e["entity_ids"])!=2 or e["entity_ids"][0]>=e["entity_ids"][1] or e["data"]!={}:
                    return False
            elif kind in ("REPLICATION_REPLAY","REPLICATION_REJECT","REPLICATION_ACCEPT"):
                if not isinstance(e["data"].get("request_id"),str) or not e["data"]["request_id"]:
                    return False
            if kind=="STEP_COMMITTED":
                if type(step) is not int or step != previous_step+1:
                    return False
                try:
                    state=state_from_dict(e["data"]["state"])
                    Engine(state=state,contract=self.contract)
                except (TypeError,ValueError,KeyError):
                    return False
                if state.step!=step:
                    return False
                snapshots[step]=state_to_dict(state)
                previous_step=step
        if self.events and (not by_step or set(by_step)!=set(range(1,previous_step+1))):
            return False
        # Audit event semantics against each committed state, not merely the hash chain.
        for step,items in by_step.items():
            if not items or items[0].get("type")!="STEP_STARTED" or items[-1].get("type")!="STEP_COMMITTED":
                return False
            phases=[e["phase"] for e in items]
            if phases!=sorted(phases) or sum(e["type"]=="STEP_STARTED" for e in items)!=1 or sum(e["type"]=="STEP_COMMITTED" for e in items)!=1:
                return False
            for phase,field in ((1,"entity_ids"),(2,"entity_ids"),(4,"entity_ids"),(5,"entity_ids")):
                rows=[e for e in items if e["phase"]==phase]
                keys=[tuple(e[field]) for e in rows]
                if keys!=sorted(keys):
                    return False
            state=state_from_dict(snapshots[step])
            start_state=state_from_dict(start_snapshots[step])
            state_vertices=state.vertices
            start_vertices=start_state.vertices
            moves={}
            for e in items:
                kind=e["type"]; data=e["data"]; ids=e.get("entity_ids",[])
                if kind=="MOVE":
                    i=ids[0]
                    if i in moves or i not in state_vertices or (data["x"],data["y"])!=(state_vertices[i].x,state_vertices[i].y):
                        return False
                    try:
                        cx,cy,clipped,corrections=clip_to_radius(data["proposed_x"],data["proposed_y"],self.contract.R_MAX_Q)
                    except (TypeError,ValueError,ArithmeticError):
                        return False
                    action_map=action_snapshots.get(step,{})
                    if i not in action_map:
                        return False
                    sx,sy=action_map[i]
                    for j in sorted(special_ids(start_vertices)):
                        if i==j:
                            continue
                        d=dist2(start_vertices[i],start_vertices[j])
                        weight=0 if d>=self.contract.h2_twice else self.contract.Q-round_even_div(self.contract.Q*d,self.contract.h2_twice)
                        sx+=round_even_div(weight*action_map[j][0],2*self.contract.Q)
                        sy+=round_even_div(weight*action_map[j][1],2*self.contract.Q)
                    if (data["proposed_x"],data["proposed_y"])!=(start_vertices[i].x+sx,start_vertices[i].y+sy):
                        return False
                    if (cx,cy)!=(data["x"],data["y"]):
                        return False
                    clips=[x for x in items if x["type"]=="BOUNDARY_CLIP" and x.get("entity_ids")==[i]]
                    if len(clips)>1 or bool(clips)!=clipped or (clipped and (clips[0]["data"]["corrections"]!=corrections or (clips[0]["data"]["x"],clips[0]["data"]["y"])!=(cx,cy))):
                        return False
                    moves[i]=data
                elif kind=="BOUNDARY_CLIP":
                    i=ids[0]
                    if i not in moves or (data["x"],data["y"])!=(moves[i]["x"],moves[i]["y"]):
                        return False
                elif kind=="SPECIAL_STATUS_CHANGE":
                    i=ids[0]
                    if i not in state_vertices or state_vertices[i].special!=data["special"]:
                        return False
                elif kind=="EDGE_ADD" and tuple(ids) not in state.edges:
                    return False
                elif kind=="EDGE_REMOVE" and tuple(ids) in state.edges:
                    return False
                elif kind in ("REPLICATION_ACCEPT","REPLICATION_REJECT"):
                    rid=data["request_id"]; result=state.processed_requests.get(rid)
                    if not isinstance(result,dict) or result.get("status")!=data.get("status") or result.get("payload")!=data.get("payload"):
                        return False
                    if kind=="REPLICATION_ACCEPT" and (result.get("child_id")!=data.get("child_id") or ids != [result.get("payload",{}).get("parent_id"),result.get("child_id")]):
                        return False
                    if kind=="REPLICATION_REJECT" and result.get("reason")!=data.get("reason"):
                        return False
                elif kind=="REPLICATION_REPLAY":
                    if data["request_id"] not in state.processed_requests:
                        return False
            # Check transition completeness against the recorded start snapshot.
            accepted=[e for e in items if e["type"]=="REPLICATION_ACCEPT"]
            rejected=[e for e in items if e["type"]=="REPLICATION_REJECT"]
            replays=[e for e in items if e["type"]=="REPLICATION_REPLAY"]
            created={e["data"].get("child_id") for e in accepted}
            if set(moves)!=set(start_vertices) or set(state_vertices)!=(set(start_vertices)|created):
                return False
            if state.step != start_state.step+1:
                return False
            for i,v in start_vertices.items():
                if i not in state_vertices:
                    return False
            # Every accepted child must match its request payload and IDs must be monotonic.
            expected_id=start_state.next_vertex_id
            for e in accepted:
                data=e["data"]; payload=data["payload"]; child_id=data["child_id"]
                if child_id!=expected_id or child_id not in state_vertices:
                    return False
                child=state_vertices[child_id]
                if (child.x,child.y)!=(payload["child_x"],payload["child_y"]):
                    return False
                expected_id+=1
            if state.next_vertex_id!=expected_id:
                return False
            # Events must exactly account for special-status and edge deltas.
            special_rows=[e for e in items if e["type"]=="SPECIAL_STATUS_CHANGE"]
            special_events={e["entity_ids"][0]:e["data"]["special"] for e in special_rows}
            if len(special_events)!=len(special_rows):
                return False
            expected_special={}
            for i,v in state_vertices.items():
                old_special=start_vertices[i].special if i in start_vertices else False
                if old_special!=v.special:
                    expected_special[i]=v.special
            if special_events!=expected_special:
                return False
            added_rows=[e for e in items if e["type"]=="EDGE_ADD"]
            removed_rows=[e for e in items if e["type"]=="EDGE_REMOVE"]
            added_events={tuple(e["entity_ids"]) for e in added_rows}
            removed_events={tuple(e["entity_ids"]) for e in removed_rows}
            if len(added_events)!=len(added_rows) or len(removed_events)!=len(removed_rows):
                return False
            if added_events != (state.edges-start_state.edges) or removed_events != (start_state.edges-state.edges):
                return False
            # Recompute every hysteretic edge transition from the two snapshots.
            all_ids=sorted(state_vertices)
            for ix,a in enumerate(all_ids):
                for b in all_ids[ix+1:]:
                    edge=(a,b)
                    d=dist2(state_vertices[a],state_vertices[b])
                    was_present=edge in start_state.edges
                    should_be_present=(d<self.contract.D_REMOVE_Q**2) if was_present else (d<=self.contract.D_ADD_Q**2)
                    if (edge in state.edges)!=should_be_present:
                        return False
            # Request ledger changes and replication events must be one-to-one.
            event_request_ids=[e["data"]["request_id"] for e in accepted+rejected]
            if len(event_request_ids)!=len(set(event_request_ids)):
                return False
            old_requests=start_state.processed_requests
            new_requests=state.processed_requests
            if any(new_requests.get(rid)!=result for rid,result in old_requests.items()):
                return False
            new_ids=set(new_requests)-set(old_requests)
            if new_ids!=set(event_request_ids):
                return False
            if any(e["data"]["request_id"] not in old_requests for e in replays):
                return False
            if any(e["data"]["request_id"] in old_requests for e in accepted+rejected):
                return False
            # Replay the replication decision procedure in canonical request-ID order.
            replication_events=[e for e in items if e["type"] in ("REPLICATION_REPLAY","REPLICATION_ACCEPT","REPLICATION_REJECT")]
            request_ids=[e["data"]["request_id"] for e in replication_events]
            if request_ids!=sorted(request_ids) or len(request_ids)!=len(set(request_ids)):
                return False
            working_positions={(state_vertices[i].x,state_vertices[i].y) for i in start_vertices}
            expected_child_id=start_state.next_vertex_id
            for event in replication_events:
                data=event["data"]; rid=data["request_id"]; payload=data["payload"]
                if not isinstance(payload,dict) or set(payload)!={"parent_id","child_x","child_y"} or any(type(payload[k]) is not int for k in payload):
                    return False
                prior=old_requests.get(rid)
                if prior is not None:
                    if event["type"]!="REPLICATION_REPLAY" or prior.get("payload")!=payload:
                        return False
                    continue
                if event["type"]=="REPLICATION_REPLAY":
                    return False
                reason=None
                parent_id=payload["parent_id"]; x=payload["child_x"]; y=payload["child_y"]
                if parent_id not in start_vertices: reason="UNKNOWN_PARENT"
                elif abs(x)>self.contract.max_coordinate_abs or abs(y)>self.contract.max_coordinate_abs: reason="COORDINATE_RANGE"
                elif not self.contract.R_Q**2 < x*x+y*y <= self.contract.R_MAX_Q**2: reason="RADIUS"
                elif (x,y) in working_positions: reason="DUPLICATE_POSITION"
                if reason is not None:
                    if event["type"]!="REPLICATION_REJECT" or data.get("reason")!=reason or data.get("status")!="rejected":
                        return False
                else:
                    if event["type"]!="REPLICATION_ACCEPT" or data.get("status")!="accepted" or data.get("child_id")!=expected_child_id:
                        return False
                    if event.get("entity_ids") != [parent_id,expected_child_id]:
                        return False
                    if (state_vertices[expected_child_id].x,state_vertices[expected_child_id].y)!=(x,y):
                        return False
                    working_positions.add((x,y))
                    expected_child_id+=1
            if expected_child_id!=state.next_vertex_id:
                return False
        expected_checkpoints = ({step for step in snapshots if step % self.contract.checkpoint_interval == 0}
                                if self.contract.checkpoint_interval > 0 else set())
        if set(self.checkpoints) != expected_checkpoints:
            return False
        for step,cp in self.checkpoints.items():
            if type(step) is not int or not isinstance(cp,dict) or set(cp)!={"step","state","state_hash"}:
                return False
            if type(cp["step"]) is not int or cp["step"]!=step or not isinstance(cp["state"],dict) or not isinstance(cp["state_hash"],str):
                return False
            try:
                if sha256_hex(canonical_bytes(cp["state"]))!=cp["state_hash"]:
                    return False
                state=state_from_dict(cp["state"])
                Engine(state=state,contract=self.contract)
            except (TypeError,ValueError,KeyError):
                return False
            if state.step!=step or snapshots.get(step)!=state_to_dict(state):
                return False
        return True
    def save_atomic(self, path, expected_current_sha256=None):
        """Atomically persist under a process lock.

        If expected_current_sha256 is provided, compare-and-swap semantics reject stale
        writers. The digest is over the exact existing file bytes; use None only when
        intentionally allowing an unconditional replacement. A missing destination is
        represented by the literal expected value "missing".
        """
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 2, "contract": contract_to_dict(self.contract),
                   "events": self.events, "checkpoints": {str(k): v for k, v in sorted(self.checkpoints.items())}}
        lock_path = dest.with_name(dest.name + ".lock")
        with _exclusive_path_lock(lock_path):
            if expected_current_sha256 is not None:
                if dest.exists():
                    current = sha256_hex(dest.read_bytes())
                else:
                    current = "missing"
                if current != expected_current_sha256:
                    raise RuntimeError("archive changed since it was read; refusing stale overwrite")
            fd, tmp = tempfile.mkstemp(prefix="." + dest.name + ".", suffix=".tmp", dir=dest.parent)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(canonical_bytes(payload))
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, dest)
                # Persist the directory entry after the atomic rename on POSIX.
                # Failure here means new content may be visible but crash durability is uncertain.
                if os.name == "posix":
                    dir_fd = os.open(dest.parent, os.O_RDONLY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
            except BaseException:
                try:
                    os.unlink(tmp)
                except FileNotFoundError:
                    pass
                raise
    @classmethod
    def load(cls,path):
        d=json.loads(Path(path).read_text(encoding="utf-8"))
        if (not isinstance(d,dict) or type(d.get("schema_version")) is not int
                or d.get("schema_version") != 2 or not isinstance(d.get("events"),list)
                or not isinstance(d.get("checkpoints"),dict) or not isinstance(d.get("contract"),dict)):
            raise ValueError("invalid archive schema")
        checkpoints={}
        for key,value in d["checkpoints"].items():
            if not isinstance(key,str) or not key.isdecimal() or str(int(key)) != key:
                raise ValueError("invalid checkpoint key")
            step=int(key)
            if step in checkpoints:
                raise ValueError("duplicate checkpoint step")
            checkpoints[step]=value
        a=cls(contract_from_dict(d["contract"])); a.events=d["events"]; a.checkpoints=checkpoints
        if not a.verify(): raise ValueError("archive integrity verification failed")
        return a

class Engine:
    def __init__(self,state=None,contract=None,archive=None):
        self.contract=contract or (archive.contract if archive is not None else Contract()); self.state=(state or initial_state()).clone(); self.archive=archive or Archive(self.contract);
        if self.archive.contract != self.contract: raise ValueError("engine/archive contract mismatch")
        self._validate(self.state)
    def _validate(self,s):
        c=self.contract
        if type(s.step) is not int or s.step<0: raise ValueError("invalid step")
        ids=list(s.vertices)
        if any(type(i) is not int or i<=0 for i in ids): raise ValueError("invalid vertex IDs")
        positions=set()
        for i,v in s.vertices.items():
            if i!=v.id or any(type(z) is not int for z in (v.id,v.x,v.y)) or type(v.special) is not bool: raise ValueError("invalid vertex fields")
            if abs(v.x)>c.max_coordinate_abs or abs(v.y)>c.max_coordinate_abs or v.x*v.x+v.y*v.y>c.rmax2: raise ValueError("vertex outside numeric bounds")
            if (v.x,v.y) in positions: raise ValueError("duplicate position")
            positions.add((v.x,v.y))
        for e in s.edges:
            if not isinstance(e,tuple) or len(e)!=2 or any(type(z) is not int for z in e) or e[0]>=e[1] or e[0] not in s.vertices or e[1] not in s.vertices: raise ValueError("invalid edge")
        if type(s.next_vertex_id) is not int or s.next_vertex_id<=max(ids,default=0): raise ValueError("non-monotonic next ID")
        if {i for i,v in s.vertices.items() if v.special}!=special_ids(s.vertices): raise ValueError("special status inconsistent")
        if not isinstance(s.processed_requests,dict): raise ValueError("invalid request ledger")
        accepted_children=set()
        allowed_rejection_reasons={"UNKNOWN_PARENT","COORDINATE_RANGE","RADIUS","DUPLICATE_POSITION"}
        for rid,result in s.processed_requests.items():
            if not isinstance(rid,str) or not rid or not isinstance(result,dict):
                raise ValueError("invalid processed request")
            status=result.get("status")
            payload=result.get("payload")
            if status not in ("accepted","rejected") or not isinstance(payload,dict):
                raise ValueError("invalid processed request result")
            if set(payload)!={"parent_id","child_x","child_y"} or any(type(payload[k]) is not int for k in payload):
                raise ValueError("invalid processed request payload")
            if status=="accepted":
                if set(result)!={"status","child_id","payload"} or type(result["child_id"]) is not int:
                    raise ValueError("invalid accepted request result")
                child_id=result["child_id"]
                parent_id=payload["parent_id"]
                if (child_id not in s.vertices or child_id <= len(_INITIAL)
                        or child_id in accepted_children or parent_id not in s.vertices):
                    raise ValueError("invalid accepted child or parent ID")
                child=s.vertices[child_id]
                if (child.x,child.y)!=(payload["child_x"],payload["child_y"]):
                    raise ValueError("accepted request does not match child position")
                accepted_children.add(child_id)
            else:
                if (set(result)!={"status","reason","payload"} or
                        not isinstance(result["reason"],str) or
                        result["reason"] not in allowed_rejection_reasons):
                    raise ValueError("invalid rejected request result")
        if accepted_children != {i for i in s.vertices if i > len(_INITIAL)}:
            raise ValueError("replicated vertices and accepted request ledger disagree")
    def step(self,inputs):
        c=self.contract; start=self.state; self._validate(start)
        if not isinstance(inputs,StepInputs): raise TypeError("StepInputs required")
        if set(inputs.direct_actions)!=set(start.vertices): raise ValueError("one action required per start-of-step vertex")
        for i,a in inputs.direct_actions.items():
            if type(i) is not int or not isinstance(a,tuple) or len(a)!=2 or any(type(z) is not int for z in a) or any(abs(z)>c.A_MAX_Q for z in a): raise ValueError("invalid action")
        requests={}
        for r in inputs.replication_requests:
            if not isinstance(r,ReplicationRequest) or not isinstance(r.request_id,str) or not r.request_id or any(type(z) is not int for z in (r.parent_id,r.child_x,r.child_y)): raise ValueError("invalid replication request")
            if r.request_id in requests and requests[r.request_id].payload()!=r.payload(): raise ValueError("request ID conflict")
            requests[r.request_id]=r
        w=start.clone(); n=start.step+1; ev=[{"step":n,"phase":0,"type":"STEP_STARTED","data":{"from_step":start.step,"contract":contract_to_dict(c),"start_state":state_to_dict(start),"actions":{str(i):list(inputs.direct_actions[i]) for i in sorted(start.vertices)}}}]
        specials=special_ids(start.vertices); proposals={}
        for i in sorted(start.vertices):
            sx,sy=inputs.direct_actions[i]
            for j in sorted(specials):
                if i==j: continue
                d=dist2(start.vertices[i],start.vertices[j]); weight=0 if d>=c.h2_twice else c.Q-round_even_div(c.Q*d,c.h2_twice)
                sx+=round_even_div(weight*inputs.direct_actions[j][0],2*c.Q); sy+=round_even_div(weight*inputs.direct_actions[j][1],2*c.Q)
            proposals[i]=(start.vertices[i].x+sx,start.vertices[i].y+sy)
        for i,(px,py) in sorted(proposals.items()):
            x,y,clipped,corr=clip_to_radius(px,py,c.R_MAX_Q); w.vertices[i].x=x; w.vertices[i].y=y
            ev.append({"step":n,"phase":1,"type":"MOVE","entity_ids":[i],"data":{"x":x,"y":y,"proposed_x":px,"proposed_y":py}})
            if clipped: ev.append({"step":n,"phase":2,"type":"BOUNDARY_CLIP","entity_ids":[i],"data":{"x":x,"y":y,"corrections":corr}})
        for rid in sorted(requests):
            r=requests[rid]; payload=r.payload(); old=w.processed_requests.get(rid)
            if old is not None:
                if old.get("payload")!=payload: raise ValueError("request ID conflicts with request ledger")
                ev.append({"step":n,"phase":3,"type":"REPLICATION_REPLAY","data":{"request_id":rid,"payload":payload}}); continue
            reason=None
            if r.parent_id not in start.vertices: reason="UNKNOWN_PARENT"
            elif abs(r.child_x)>c.max_coordinate_abs or abs(r.child_y)>c.max_coordinate_abs: reason="COORDINATE_RANGE"
            elif not c.r2<r.child_x*r.child_x+r.child_y*r.child_y<=c.rmax2: reason="RADIUS"
            elif any(v.x==r.child_x and v.y==r.child_y for v in w.vertices.values()): reason="DUPLICATE_POSITION"
            if reason: result={"status":"rejected","reason":reason,"payload":payload}; ev.append({"step":n,"phase":3,"type":"REPLICATION_REJECT","data":{"request_id":rid,**result}})
            else:
                vid=w.next_vertex_id; w.next_vertex_id+=1; w.vertices[vid]=Vertex(vid,r.child_x,r.child_y,False)
                result={"status":"accepted","child_id":vid,"payload":payload}; ev.append({"step":n,"phase":3,"type":"REPLICATION_ACCEPT","entity_ids":[r.parent_id,vid],"data":{"request_id":rid,**result}})
            w.processed_requests[rid]=result
        wanted=special_ids(w.vertices)
        for i,v in w.vertices.items():
            flag=i in wanted
            if v.special!=flag: v.special=flag; ev.append({"step":n,"phase":4,"type":"SPECIAL_STATUS_CHANGE","entity_ids":[i],"data":{"special":flag}})
        edges=set(w.edges); ids=sorted(w.vertices)
        for ix,a in enumerate(ids):
            for b in ids[ix+1:]:
                edge=(a,b); d=dist2(w.vertices[a],w.vertices[b])
                if edge not in edges and d<=c.add2: edges.add(edge); ev.append({"step":n,"phase":5,"type":"EDGE_ADD","entity_ids":[a,b],"data":{}})
                elif edge in edges and d>=c.remove2: edges.remove(edge); ev.append({"step":n,"phase":5,"type":"EDGE_REMOVE","entity_ids":[a,b],"data":{}})
        w.edges=edges; w.step=n; self._validate(w)
        ev.append({"step":n,"phase":8,"type":"STEP_COMMITTED","data":{"state":state_to_dict(w)}})
        # Stage every in-memory write before publishing any part of the step.
        sealed=self.archive.prepare_bundle(ev)
        staged_events=self.archive.events+[dict(item) for item in sealed]
        staged_checkpoints=dict(self.archive.checkpoints)
        if c.checkpoint_interval>0 and n%c.checkpoint_interval==0:
            payload=state_to_dict(w)
            staged_checkpoints[n]={"step":n,"state":payload,"state_hash":sha256_hex(canonical_bytes(payload))}
        # Publish the completed bundle as a single commit point.
        self.archive.events=staged_events
        self.archive.checkpoints=staged_checkpoints
        self.state=w
        return w.clone()


def verify_chain(events, genesis="0"*64):
    if not isinstance(events, list) or not isinstance(genesis, str):
        return False
    previous=genesis
    for event in events:
        if not isinstance(event,dict) or event.get("previous_hash")!=previous: return False
        body=dict(event); actual=body.pop("event_hash",None)
        if not isinstance(actual,str):
            return False
        try:
            if sha256_hex(canonical_bytes(body))!=actual:
                return False
        except (TypeError, ValueError, OverflowError):
            return False
        previous=actual
    return True
