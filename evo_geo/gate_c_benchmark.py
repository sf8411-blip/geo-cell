"""Gate C: frozen-candidate held-out scoring and reproducible benchmark reports.

The scorer receives frozen predictions only after training-time search has finished.
It never feeds held-out labels back into candidate generation or revises a candidate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import random
from typing import Callable, Iterable

from evo_geo.operator_discovery import (
    Observation, check_counterexamples, enumerate_candidates, evaluate, search,
)

BENCHMARK_VERSION = "gate-c-v1"
X_MIN, X_MAX = -16, 16


@dataclass(frozen=True)
class TrialConfig:
    seed: int = 20261030
    candidate_budget: int = 1000
    max_cost: int = 4
    min_distinct_inputs: int = 4

    def __post_init__(self):
        if type(self.seed) is not int:
            raise ValueError("seed must be an integer")
        if type(self.candidate_budget) is not int or not 1 <= self.candidate_budget <= 2000:
            raise ValueError("candidate_budget must be in [1, 2000]")
        if type(self.max_cost) is not int or not 1 <= self.max_cost <= 4:
            raise ValueError("max_cost must be in [1, 4]")
        if type(self.min_distinct_inputs) is not int or self.min_distinct_inputs < 1:
            raise ValueError("min_distinct_inputs must be positive")


def target_label(family: str, x: int, seed: int = 0) -> int:
    """Scorer-only target definitions; callers must not pass these to search."""
    if family == "parity":
        return x % 2
    if family == "threshold":
        return int(x >= 0)
    if family == "negative":
        return int(x < 0)
    if family == "seeded_noise":
        return random.Random(f"{seed}:{x}").randint(0, 1)
    raise ValueError(f"unknown target family: {family}")


def _dataset_digest(rows: Iterable[Observation]) -> str:
    payload = [{"x": o.x, "y": o.y} for o in sorted(rows, key=lambda o: (o.x, o.y))]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _error_rate(rows: tuple[Observation, ...], predictions: tuple[int | None, ...]) -> float | None:
    if not rows:
        return None
    return sum(p is None or p != o.y for o, p in zip(rows, predictions)) / len(rows)


def score_frozen_predictions(rows: Iterable[Observation], predictions: Iterable[int | None]) -> dict:
    """Score a frozen prediction vector. Does not alter the vector or candidate."""
    data, pred = tuple(rows), tuple(predictions)
    if len(data) != len(pred):
        raise ValueError("one frozen prediction is required per observation")
    errors = [
        {"x": o.x, "expected": o.y, "predicted": p}
        for o, p in zip(data, pred) if p is None or p != o.y
    ]
    return {
        "n": len(data),
        "error_count": len(errors),
        "error_rate": (len(errors) / len(data)) if data else None,
        "abstention_count": sum(p is None for p in pred),
        "counterexamples": errors,
        "dataset_digest": _dataset_digest(data),
    }


def _predictions(expression: str | None, rows: tuple[Observation, ...]) -> tuple[int | None, ...]:
    if expression is None:
        return tuple(None for _ in rows)
    pool = {e.canonical(): e for e in enumerate_candidates(max_cost=4, max_candidates=2000)}
    expr = pool.get(expression)
    if expr is None:
        return tuple(None for _ in rows)
    result = []
    for row in rows:
        try:
            result.append(evaluate(expr, row.x))
        except (ArithmeticError, TypeError, ValueError):
            result.append(None)
    return tuple(result)


def run_trial(family: str, config: TrialConfig = TrialConfig()) -> dict:
    """Run one preregistered split. Test labels are created only after search freezes."""
    all_x = tuple(range(X_MIN, X_MAX + 1))
    # Training covers the central region; held-out inputs are disjoint and include
    # an extrapolation/distribution-shift region at both ends.
    train_x = tuple(x for x in all_x if -8 <= x <= 8)
    test_x = tuple(x for x in all_x if x < -8 or x > 8)
    train = tuple(Observation(x, target_label(family, x, config.seed)) for x in train_x)

    # Search receives training observations only. Freeze selected expression and ID
    # before any held-out labels are constructed.
    result = search(
        train,
        max_cost=config.max_cost,
        max_candidates=config.candidate_budget,
        min_distinct_inputs=config.min_distinct_inputs,
    )
    frozen_expression = result.selected
    frozen_id = result.selected_id
    frozen_record = {
        "expression": frozen_expression,
        "candidate_id": frozen_id,
        "grammar_version": result.grammar_version,
        "training_observation_digest": result.observation_digest,
        "candidate_count": result.candidate_count,
        "status": result.status,
    }

    # Only now construct scorer-only labels and evaluate the immutable prediction
    # vector. There is intentionally no path from this result back to search().
    test = tuple(Observation(x, target_label(family, x, config.seed)) for x in test_x)
    frozen_predictions = _predictions(frozen_expression, test)
    heldout = score_frozen_predictions(test, frozen_predictions)

    counterexample_audit = None
    disposition = "abstained" if frozen_expression is None else "not_falsified_on_this_split"
    if frozen_expression is not None and heldout["error_count"] > 0:
        counterexample_audit = check_counterexamples(
            frozen_expression,
            tuple(Observation(item["x"], item["expected"]) for item in heldout["counterexamples"]),
        )
        disposition = "rejected_by_heldout_counterexample"

    # Baselines are evaluated on the same held-out set. These simple fixed rules
    # have no fitting step; random baseline is reproducibly selected from a bounded
    # candidate list using the declared seed and training labels only.
    baseline_rows = {}
    for name, expression in (("constant_zero", "0"), ("constant_one", "1"), ("identity_x", "x")):
        baseline_rows[name] = score_frozen_predictions(test, _predictions(expression, test))

    candidates = enumerate_candidates(config.max_cost, config.candidate_budget)
    rng = random.Random(config.seed)
    random_order = list(candidates)
    rng.shuffle(random_order)
    train_by_x = {o.x: o.y for o in train}
    random_choice = None
    random_train_error = None
    for expr in random_order:
        try:
            errs = sum(evaluate(expr, x) != y for x, y in train_by_x.items())
        except (ArithmeticError, TypeError, ValueError):
            continue
        rate = errs / len(train)
        if random_train_error is None or rate < random_train_error:
            random_choice, random_train_error = expr.canonical(), rate
        if rate == 0:
            break
    baseline_rows["seeded_random_search"] = score_frozen_predictions(
        test, _predictions(random_choice, test)
    )
    baseline_rows["seeded_random_search"]["training_error_rate"] = random_train_error

    return {
        "benchmark_version": BENCHMARK_VERSION,
        "target_family": family,
        "config": asdict(config),
        "split": {
            "train_x": list(train_x),
            "test_x": list(test_x),
            "train_digest": _dataset_digest(train),
            "test_digest": _dataset_digest(test),
            "overlap": sorted(set(train_x).intersection(test_x)),
        },
        "frozen_candidate": frozen_record,
        "training_error_rate": result.training_error,
        "heldout": heldout,
        "disposition": disposition,
        "counterexample_audit": counterexample_audit,
        "baselines": baseline_rows,
        "limitations": [
            "Synthetic bounded integer benchmark only; not evidence of general intelligence.",
            "The fixed target families and finite grammar do not establish open-ended discovery.",
            "Held-out failure is reported, not repaired using the same test labels.",
            "Declared seed provides replayability for this implementation, not cryptographic provenance.",
        ],
    }


def run_benchmark(config: TrialConfig = TrialConfig()) -> dict:
    """Run all preregistered target families and emit JSON-serializable records."""
    families = ("parity", "threshold", "negative", "seeded_noise")
    trials = [run_trial(family, config) for family in families]
    payload = {
        "benchmark_version": BENCHMARK_VERSION,
        "config": asdict(config),
        "trial_count": len(trials),
        "trials": trials,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["report_digest"] = hashlib.sha256(canonical.encode()).hexdigest()
    return payload
