"""Gate B: deterministic bounded expression enumeration; no grammar mutation."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from typing import Iterable

GRAMMAR_VERSION = "gate-b-int-bool-v1"
MIN_X, MAX_X = -16, 16
MAX_ABS_INTERMEDIATE = 1_000_000

@dataclass(frozen=True, order=True)
class Observation:
    x: int
    y: int
    def __post_init__(self):
        if type(self.x) is not int or not MIN_X <= self.x <= MAX_X:
            raise ValueError(f"x must be an integer in [{MIN_X}, {MAX_X}]")
        if type(self.y) is not int or self.y not in (0, 1):
            raise ValueError("y must be integer 0 or 1")

@dataclass(frozen=True)
class Expr:
    op: str
    args: tuple["Expr", ...] = ()
    value: int | None = None
    kind: str = "int"
    def canonical(self):
        if self.op == "var": return "x"
        if self.op == "const": return str(self.value)
        if self.op == "not": return f"(not {self.args[0].canonical()})"
        symbols = {"add":"+","sub":"-","mul":"*","mod":"%","eq":"==","lt":"<","and":"and","or":"or"}
        return f"({self.args[0].canonical()} {symbols[self.op]} {self.args[1].canonical()})"
    @property
    def cost(self):
        return 1 if self.op in {"var", "const"} else 1 + sum(a.cost for a in self.args)
    @property
    def candidate_id(self):
        return hashlib.sha256((GRAMMAR_VERSION + "|" + self.canonical()).encode()).hexdigest()

X = Expr("var")
LEAVES = (X,) + tuple(Expr("const", value=n) for n in range(-2, 5))

def _eval(expr: Expr, x: int):
    if expr.op == "var": return x
    if expr.op == "const": return expr.value
    values = [_eval(a, x) for a in expr.args]
    if expr.op == "not": return not bool(values[0])
    a, b = values[0], values[1] if len(values) > 1 else None
    if expr.op == "add": out = int(a) + int(b)
    elif expr.op == "sub": out = int(a) - int(b)
    elif expr.op == "mul": out = int(a) * int(b)
    elif expr.op == "mod":
        if int(b) <= 0: raise ArithmeticError("modulus must be positive")
        out = int(a) % int(b)
    elif expr.op == "eq": return a == b
    elif expr.op == "lt": return int(a) < int(b)
    elif expr.op == "and": return bool(a) and bool(b)
    elif expr.op == "or": return bool(a) or bool(b)
    else: raise ValueError("unknown operator")
    if abs(out) > MAX_ABS_INTERMEDIATE: raise ArithmeticError("intermediate limit exceeded")
    return out

def evaluate(expr: Expr, x: int) -> int:
    if type(x) is not int or not MIN_X <= x <= MAX_X:
        raise ValueError("input outside observation contract")
    value = _eval(expr, x)
    if type(value) is bool: return int(value)
    if type(value) is not int or value not in (0, 1):
        raise ValueError("candidate output must be binary")
    return value

def _binary(op, left, right, kind):
    if op in {"add", "mul", "eq", "and", "or"} and right.canonical() < left.canonical():
        left, right = right, left
    return Expr(op, (left, right), kind=kind)

def enumerate_candidates(max_cost: int = 4, max_candidates: int = 2000):
    if type(max_cost) is not int or not 1 <= max_cost <= 4: raise ValueError("max_cost must be an integer in [1, 4] for the bounded Gate B grammar")
    if type(max_candidates) is not int or max_candidates < 1: raise ValueError("max_candidates must be positive")
    by_cost = {1: {e.canonical(): e for e in LEAVES}}
    ordered = sorted(by_cost[1].values(), key=lambda e: e.canonical())
    seen = {e.canonical() for e in ordered}
    if len(ordered) >= max_candidates: return tuple(ordered[:max_candidates])
    specs = (("add","int","int"),("sub","int","int"),("mul","int","int"),
             ("mod","int","int"),("eq","bool","int"),("lt","bool","int"),
             ("and","bool","bool"),("or","bool","bool"))
    for cost in range(2, max_cost + 1):
        layer = {}
        for child in by_cost.get(cost - 1, {}).values():
            if child.kind == "bool":
                e = Expr("not", (child,), kind="bool")
                layer[e.canonical()] = e
        for op, out_kind, in_kind in specs:
            for lc in range(1, cost - 1):
                rc = cost - 1 - lc
                for left in by_cost.get(lc, {}).values():
                    for right in by_cost.get(rc, {}).values():
                        if left.kind != in_kind or right.kind != in_kind: continue
                        if op == "mod" and (right.op != "const" or right.value is None or right.value <= 0): continue
                        e = _binary(op, left, right, out_kind)
                        layer[e.canonical()] = e
            if op in {"add","mul","eq","and","or"} and (cost - 1) % 2 == 0:
                half = (cost - 1) // 2
                pool = sorted(by_cost.get(half, {}).values(), key=lambda e: e.canonical())
                for i, left in enumerate(pool):
                    for right in pool[i:]:
                        if left.kind != in_kind or right.kind != in_kind: continue
                        e = _binary(op, left, right, out_kind)
                        layer[e.canonical()] = e
        by_cost[cost] = {}
        for name, expr in sorted(layer.items()):
            if name in seen: continue
            seen.add(name); by_cost[cost][name] = expr; ordered.append(expr)
            if len(ordered) >= max_candidates: return tuple(ordered)
    return tuple(ordered)

@dataclass(frozen=True)
class SearchResult:
    status: str
    selected: str | None
    selected_id: str | None
    candidate_count: int
    matching_candidates: tuple[str, ...]
    rejected_by_counterexample: tuple[str, ...]
    training_error: float | None
    grammar_version: str
    observation_digest: str
    log: tuple[dict, ...]
    def to_dict(self):
        return {"status":self.status,"selected":self.selected,"selected_id":self.selected_id,
                "candidate_count":self.candidate_count,"matching_candidates":list(self.matching_candidates),
                "rejected_by_counterexample":list(self.rejected_by_counterexample),
                "training_error":self.training_error,"grammar_version":self.grammar_version,
                "observation_digest":self.observation_digest,"log":list(self.log)}

def search(observations: Iterable[Observation], *, max_cost=4, max_candidates=2000,
           min_distinct_inputs=4, initial_candidates=("x","0","1")):
    obs = tuple(observations)
    if type(min_distinct_inputs) is not int or min_distinct_inputs < 1:
        raise ValueError("min_distinct_inputs must be positive")
    payload = [{"x":o.x,"y":o.y} for o in sorted(obs, key=lambda o:(o.x,o.y))]
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",",":")).encode()).hexdigest()
    by_x = {}
    for o in obs: by_x.setdefault(o.x,set()).add(o.y)
    reason = "contradictory_observations" if any(len(v)>1 for v in by_x.values()) else None
    if reason is None and len(by_x) < min_distinct_inputs: reason = "insufficient_distinct_inputs"
    if reason:
        return SearchResult("insufficient_evidence",None,None,0,(),(),None,GRAMMAR_VERSION,digest,
                            ({"event":"abstain","reason":reason},))
    candidates = enumerate_candidates(max_cost, max_candidates)
    matches, rejected, log = [], [], []
    initial = set(initial_candidates)
    for expr in candidates:
        try: predictions = [evaluate(expr,o.x) for o in obs]
        except (ArithmeticError,TypeError,ValueError):
            log.append({"candidate":expr.canonical(),"event":"rejected","reason":"evaluation_error"}); continue
        errors = sum(p != o.y for p,o in zip(predictions,obs))
        log.append({"candidate":expr.canonical(),"candidate_id":expr.candidate_id,
                    "event":"evaluated","errors":errors,"syntax_cost":expr.cost})
        if errors: rejected.append(expr.canonical())
        elif expr.canonical() not in initial: matches.append(expr)
    if not matches:
        return SearchResult("insufficient_evidence",None,None,len(candidates),(),tuple(rejected),None,
                            GRAMMAR_VERSION,digest,tuple(log))
    matches.sort(key=lambda e:(e.cost,e.canonical()))
    chosen = matches[0]
    return SearchResult("candidate_found",chosen.canonical(),chosen.candidate_id,len(candidates),
                        tuple(e.canonical() for e in matches),tuple(rejected),0.0,GRAMMAR_VERSION,digest,tuple(log))

def check_counterexamples(expression: str, observations: Iterable[Observation]):
    pool = {e.canonical():e for e in enumerate_candidates(max_cost=4,max_candidates=2000)}
    if expression not in pool: return {"status":"unknown_candidate","expression":expression,"contradictions":[]}
    expr = pool[expression]; contradictions = []
    for o in observations:
        try: prediction = evaluate(expr,o.x)
        except (ArithmeticError,TypeError,ValueError): prediction = None
        if prediction != o.y: contradictions.append({"x":o.x,"y":o.y,"prediction":prediction})
    return {"status":"rejected" if contradictions else "not_falsified_by_supplied_evidence",
            "expression":expression,"candidate_id":expr.candidate_id,"contradictions":contradictions}
