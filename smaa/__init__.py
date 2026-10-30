"""SMAA: auditable functional self-modeling, not a consciousness claim."""
from __future__ import annotations
import hashlib, json
from dataclasses import asdict, dataclass, field
from typing import Any
GENESIS="0"*64
def _canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def _event_hash(seq,kind,actor,tick,payload,prev):
    return hashlib.sha256(_canon({"sequence":seq,"event_type":kind,"actor_id":actor,"timestamp":tick,"payload":payload,"previous_hash":prev}).encode()).hexdigest()
@dataclass(frozen=True)
class Capability:
    name:str; tested_success_rate:float; trials:int; evidence_ids:tuple[str,...]=(); limitations:tuple[str,...]=()
    def __post_init__(self):
        if not self.name or not 0<=self.tested_success_rate<=1 or self.trials<0: raise ValueError("invalid capability")
@dataclass(frozen=True)
class CellRecord:
    cell_id:str; joined_at:int; capabilities:tuple[str,...]=(); active:bool=True
@dataclass(frozen=True)
class KnowledgeClaim:
    claim_id:str; proposition:str; owner_cell_id:str; evidence_ids:tuple[str,...]=(); verified:bool=False
@dataclass(frozen=True)
class Prediction:
    prediction_id:str; target:str; probability:float; predicted_value:Any=None; context_id:str=""
    def __post_init__(self):
        if not self.prediction_id or not 0<=self.probability<=1: raise ValueError("probability must be in [0,1]")
@dataclass(frozen=True)
class Event:
    sequence:int; event_type:str; actor_id:str; timestamp:int; payload:dict; previous_hash:str; event_hash:str
@dataclass
class SelfModel:
    network_id:str; version:int=1; tick:int=0
    cells:dict[str,CellRecord]=field(default_factory=dict)
    capabilities:dict[str,Capability]=field(default_factory=dict)
    knowledge:dict[str,KnowledgeClaim]=field(default_factory=dict)
    resources:dict[str,float]=field(default_factory=dict)
    unknowns:list[str]=field(default_factory=list)
    model_assumptions:list[str]=field(default_factory=list)
    last_revision_reason:str|None=None
    def snapshot(self):
        return {"network_id":self.network_id,"version":self.version,"tick":self.tick,
          "cells":{k:asdict(v) for k,v in sorted(self.cells.items())},
          "capabilities":{k:asdict(v) for k,v in sorted(self.capabilities.items())},
          "knowledge":{k:asdict(v) for k,v in sorted(self.knowledge.items())},
          "resources":dict(sorted(self.resources.items())),"unknowns":sorted(self.unknowns),
          "model_assumptions":list(self.model_assumptions),"last_revision_reason":self.last_revision_reason}
class EventLedger:
    """Hash chaining detects tampering against a trusted head; it is not a signature."""
    def __init__(self): self.events=[]
    def append(self,kind,actor,tick,payload):
        if not kind or not actor or tick<0: raise ValueError("invalid event metadata")
        seq=len(self.events); prev=self.events[-1].event_hash if self.events else GENESIS
        safe=json.loads(_canon(payload)); h=_event_hash(seq,kind,actor,tick,safe,prev)
        e=Event(seq,kind,actor,tick,safe,prev,h); self.events.append(e); return e
    def verify(self):
        prev=GENESIS
        for i,e in enumerate(self.events):
            if e.sequence!=i or e.previous_hash!=prev or _event_hash(e.sequence,e.event_type,e.actor_id,e.timestamp,e.payload,e.previous_hash)!=e.event_hash: return False
            prev=e.event_hash
        return True
def brier_score(probabilities,outcomes):
    if len(probabilities)!=len(outcomes) or not probabilities: raise ValueError("non-empty paired samples required")
    if any(not 0<=p<=1 for p in probabilities) or any(y not in (0,1,False,True) for y in outcomes): raise ValueError("invalid samples")
    return sum((float(p)-int(y))**2 for p,y in zip(probabilities,outcomes))/len(probabilities)
def expected_calibration_error(probabilities,outcomes,bins=10):
    if len(probabilities)!=len(outcomes) or not probabilities or bins<1: raise ValueError("invalid calibration sample")
    if any(not 0<=p<=1 for p in probabilities) or any(y not in (0,1,False,True) for y in outcomes): raise ValueError("invalid samples")
    n=len(probabilities); total=0.0
    for i in range(bins):
        ids=[j for j,p in enumerate(probabilities) if i/bins<=p<(i+1)/bins or (i==bins-1 and p==1)]
        if ids:
            conf=sum(probabilities[j] for j in ids)/len(ids); acc=sum(int(outcomes[j]) for j in ids)/len(ids)
            total+=len(ids)/n*abs(conf-acc)
    return total
def normalized_prediction_error(predicted,actual,weights=None):
    keys=set(predicted)&set(actual)
    if not keys: raise ValueError("no common state dimensions")
    weights=weights or {}; denom=sum(weights.get(k,1.0) for k in keys)
    if denom<=0: raise ValueError("positive weight required")
    total=0.0
    for k in keys:
        a,b=predicted[k],actual[k]
        err=min(1.0,abs(float(a)-float(b))/max(1.0,abs(float(b)))) if isinstance(a,(int,float)) and isinstance(b,(int,float)) else (0.0 if a==b else 1.0)
        total+=weights.get(k,1.0)*err
    return total/denom
class SMAAEngine:
    """Network-level reference engine. Private observations are not accepted by its API."""
    def __init__(self,network_id):
        if not network_id: raise ValueError("network_id required")
        self.model=SelfModel(network_id); self.ledger=EventLedger(); self.predictions={}
    def _event(self,kind,actor,payload): return self.ledger.append(kind,actor,self.model.tick,payload)
    def register_cell(self,cell_id,capabilities=(),actor_id="network"):
        if not cell_id or cell_id in self.model.cells: raise ValueError("cell id must be unique")
        rec=CellRecord(cell_id,self.model.tick,tuple(sorted(set(capabilities))),True); self.model.cells[cell_id]=rec
        self._event("cell_joined",actor_id,{"cell_id":cell_id,"capabilities":list(rec.capabilities)})
    def deactivate_cell(self,cell_id,actor_id="network"):
        rec=self.model.cells.get(cell_id)
        if rec is None or not rec.active: raise ValueError("unknown or inactive cell")
        self.model.cells[cell_id]=CellRecord(rec.cell_id,rec.joined_at,rec.capabilities,False)
        self._event("cell_deactivated",actor_id,{"cell_id":cell_id})
    def add_capability(self,capability,actor_id="network"):
        self.model.capabilities[capability.name]=capability; self._event("capability_evidence_added",actor_id,asdict(capability))
    def add_knowledge_claim(self,claim,actor_id):
        if claim.owner_cell_id not in self.model.cells: raise ValueError("claim owner is not registered")
        self.model.knowledge[claim.claim_id]=claim
        self._event("knowledge_claim_added",actor_id,{"claim_id":claim.claim_id,"owner_cell_id":claim.owner_cell_id,"verified":claim.verified,"evidence_ids":list(claim.evidence_ids)})
    def receive_public_summary(self,cell_id,summary):
        forbidden={"local_evidence","raw_observations","private_memory","training_examples","hidden_labels"}
        if forbidden.intersection(summary): raise ValueError("private evidence must not cross cell boundary")
        if cell_id not in self.model.cells: raise ValueError("unknown cell")
        allowed={"resource_cpu","resource_memory","reported_unknowns","capability_names"}
        if set(summary)-allowed: raise ValueError("unsupported summary fields")
        for k in ("resource_cpu","resource_memory"):
            if k in summary:
                v=float(summary[k])
                if not 0<=v<=1: raise ValueError("resource fraction outside [0,1]")
                self.model.resources[f"{cell_id}.{k}"]=v
        for item in summary.get("reported_unknowns",[]):
            if item not in self.model.unknowns: self.model.unknowns.append(str(item))
        self._event("public_summary_received",cell_id,{"fields":sorted(summary)})
    def record_prediction(self,prediction,actor_id="network"):
        if prediction.prediction_id in self.predictions: raise ValueError("duplicate prediction")
        self.predictions[prediction.prediction_id]=prediction
        self._event("prediction_recorded",actor_id,{"prediction_id":prediction.prediction_id,"target":prediction.target,"probability":prediction.probability,"predicted_value":prediction.predicted_value,"context_id":prediction.context_id})
    def resolve_prediction(self,prediction_id,outcome,actor_id="evaluator"):
        p=self.predictions.pop(prediction_id); score=(p.probability-int(bool(outcome)))**2
        self._event("prediction_resolved",actor_id,{"prediction_id":prediction_id,"outcome":bool(outcome),"brier_component":score})
        return {"prediction_id":prediction_id,"brier_component":score,"outcome":bool(outcome)}
    def predict_state(self,action,observation=None):
        return {"active_cells":sum(c.active for c in self.model.cells.values()),"cell_ids":sorted(k for k,v in self.model.cells.items() if v.active),"version":self.model.version,"resources":dict(sorted(self.model.resources.items())),"last_action_type":action.get("type","unknown"),"observation_keys":sorted((observation or {}).keys())}
    def observe_actual_state(self,actual,predicted,actor_id="evaluator"):
        err=normalized_prediction_error(predicted,actual)
        self._event("self_prediction_error",actor_id,{"error":err,"predicted_keys":sorted(predicted),"actual_keys":sorted(actual)})
        return err
    def revise_self_model(self,reason,assumptions,actor_id="network"):
        if not reason.strip(): raise ValueError("revision requires evidence-based reason")
        old=self.model.version; self.model.version+=1; self.model.model_assumptions=list(assumptions); self.model.last_revision_reason=reason
        self._event("self_model_revised",actor_id,{"from_version":old,"to_version":self.model.version,"reason":reason,"assumptions":assumptions})
    def identity_report(self):
        return {"network_id":self.model.network_id,"model_version":self.model.version,"active_cells":sorted(k for k,v in self.model.cells.items() if v.active),"inactive_cells":sorted(k for k,v in self.model.cells.items() if not v.active),"capabilities":sorted(self.model.capabilities),"known_claims":sorted(self.model.knowledge),"unknowns":sorted(self.model.unknowns)}
    def social_knowledge_view(self,viewer_cell_id):
        if viewer_cell_id not in self.model.cells: raise ValueError("unknown viewer")
        return {"owned":sorted(c.claim_id for c in self.model.knowledge.values() if c.owner_cell_id==viewer_cell_id),"shared_verified":sorted(c.claim_id for c in self.model.knowledge.values() if c.verified),"other_unverified":sorted(c.claim_id for c in self.model.knowledge.values() if c.owner_cell_id!=viewer_cell_id and not c.verified)}
    def audit(self): return {"ledger_valid":self.ledger.verify(),"event_count":len(self.ledger.events),"model":self.model.snapshot()}
def run_reference_suite():
    e=SMAAEngine("smaa-reference-network"); e.register_cell("cell-A",["counting"]); e.register_cell("cell-B",["geometry"])
    before=e.identity_report(); e.register_cell("cell-C",["geometry"]); after=e.identity_report()
    t1=before["active_cells"]==["cell-A","cell-B"] and after["active_cells"]==["cell-A","cell-B","cell-C"]
    e.deactivate_cell("cell-C",actor_id="cell-A"); t2=e.ledger.events[-1].actor_id=="cell-A"
    t3=e.identity_report()["inactive_cells"]==["cell-C"] and e.identity_report()["network_id"]=="smaa-reference-network"
    e.model.unknowns.append("unseen-domain-X"); t4="unseen-domain-X" in e.identity_report()["unknowns"]
    e.record_prediction(Prediction("p1","task-success",.8),"cell-A"); resolved=e.resolve_prediction("p1",True); t5=abs(resolved["brier_component"]-.04)<1e-12
    pred=e.predict_state({"type":"no-op"}); actual=dict(pred); actual["active_cells"]=1; err=e.observe_actual_state(actual,pred); t6=err>0
    e.add_knowledge_claim(KnowledgeClaim("k1","geometry relation","cell-B",("ev-1",),False),"cell-B")
    social=e.social_knowledge_view("cell-A"); t7=social["other_unverified"]==["k1"] and social["owned"]==[]
    e.revise_self_model("prediction mismatch in active cell count",["active membership can change after intervention"]); t8=e.model.version==2
    probs=[.8,.7,.2,.1]; outcomes=[1,1,0,0]
    return {"suite":"SMAA-reference-0.1","tests":{"self_other":t1,"agency_attribution":t2,"identity_continuity":t3,"limitation_tracking":t4,"metacognitive_recording":t5,"self_prediction_error":t6,"social_knowledge_provenance":t7,"structural_self_revision":t8},"metrics":{"brier_score":brier_score(probs,outcomes),"ece":expected_calibration_error(probs,outcomes),"self_prediction_error":err},"audit":e.audit()}
__all__=["SMAAEngine","EventLedger","Capability","CellRecord","KnowledgeClaim","Prediction","SelfModel","brier_score","expected_calibration_error","normalized_prediction_error","run_reference_suite"]
