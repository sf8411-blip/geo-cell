"""Held-out and adversarial evidence benchmark (finite grammar, not open-ended discovery).

The evaluator chooses from hidden target rules, including some deliberately
outside the learner's finite candidate grammar. This tests generalization and
model misspecification, not unrestricted invention of a new representation.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import random
from typing import Callable

DOMAIN = tuple(range(64))


@dataclass(frozen=True)
class Rule:
    name: str
    fn: Callable[[int], int]

    def __call__(self, x: int) -> int:
        return self.fn(x)


def target_rules() -> tuple[Rule, ...]:
    """Evaluator-only targets; several are deliberately outside the learner grammar."""
    return (
        Rule("target_parity", lambda x: x % 2),
        Rule("target_threshold", lambda x: int(x >= 32)),
        Rule("target_prime_indicator", lambda x: int(
            x >= 2 and all(x % d for d in range(2, int(x ** 0.5) + 1))
        )),
        Rule("target_xor_mod3_threshold", lambda x: int((x % 3 == 1) != (x >= 32))),
        Rule("target_and_block_mod3", lambda x: int((x % 3 == 2) and ((x // 4) % 2 == 1))),
    )


def candidate_rules() -> tuple[Rule, ...]:
    """Finite, explicit grammar available to the learner; not all targets are representable."""
    rules = [
        Rule("parity", lambda x: x % 2),
        Rule("bit_count_parity", lambda x: x.bit_count() % 2),
    ]
    rules.extend(
        Rule(f"mod3_eq_{r}", lambda x, r=r: int(x % 3 == r))
        for r in range(3)
    )
    rules.extend(
        Rule(f"threshold_{t}", lambda x, t=t: int(x >= t))
        for t in (8, 16, 24, 32, 40, 48, 56)
    )
    rules.extend(
        Rule(f"block_{k}", lambda x, k=k: (x // k) % 2)
        for k in (2, 3, 4, 5, 6, 7, 8, 9)
    )
    return tuple(rules)


def wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> list[float]:
    """Two-sided 95% Wilson score interval for a binomial proportion."""
    if trials <= 0:
        return [0.0, 1.0]
    p = successes / trials
    denom = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denom
    half = z * ((p * (1.0 - p) / trials + z * z / (4.0 * trials * trials)) ** 0.5) / denom
    return [max(0.0, center - half), min(1.0, center + half)]


def _error(rule: Rule, labels: dict[int, int], xs: tuple[int, ...]) -> float:
    if not xs:
        return 0.0
    return sum(rule(x) != labels[x] for x in xs) / len(xs)


def run_trial(seed: int, train_size: int = 16, adversarial_fraction: float = 0.0) -> dict:
    """One seeded trial. The scorer retains the target label; selection sees only training data."""
    if not 4 <= train_size < len(DOMAIN):
        raise ValueError("train_size must be in [4, len(DOMAIN)-1]")
    if not 0.0 <= adversarial_fraction <= 1.0:
        raise ValueError("adversarial_fraction must be in [0, 1]")

    rng = random.Random(seed)
    rules = candidate_rules()
    target = rng.choice(target_rules())
    shuffled = list(DOMAIN)
    rng.shuffle(shuffled)
    train_x = tuple(sorted(shuffled[:train_size]))
    heldout_x = tuple(sorted(shuffled[train_size:]))
    truth = {x: target(x) for x in DOMAIN}
    observed = dict(truth)

    # Adversarial reporters flip a reproducible subset of training labels only.
    n_flip = round(len(train_x) * adversarial_fraction)
    flipped_x = set(rng.sample(list(train_x), n_flip)) if n_flip else set()
    for x in flipped_x:
        observed[x] = 1 - observed[x]

    # Deterministic empirical-risk minimization. Ties are explicitly reported.
    ranked = sorted(
        ((_error(rule, observed, train_x), rule.name, rule) for rule in rules),
        key=lambda row: (row[0], row[1]),
    )
    best_train_error, _, selected = ranked[0]
    tied = [row[2].name for row in ranked if abs(row[0] - best_train_error) < 1e-12]
    heldout_error = _error(selected, truth, heldout_x)
    exact_match = all(selected(x) == target(x) for x in DOMAIN)
    train_fit = best_train_error == 0.0
    return {
        "seed": seed,
        "target_rule": target.name,
        "selected_rule": selected.name,
        "train_error_observed": best_train_error,
        "heldout_error_clean_labels": heldout_error,
        "exact_rule_match": exact_match,
        "perfect_training_fit": train_fit,
        "false_acceptance": train_fit and heldout_error > 0.0,
        "ambiguous_minimizers": len(tied) > 1,
        "minimizer_count": len(tied),
        "flipped_training_labels": len(flipped_x),
        "train_size": len(train_x),
        "heldout_size": len(heldout_x),
    }


def run_benchmark(
    trials: int = 200,
    seed: int = 20261030,
    train_size: int = 16,
    attack_rates: tuple[float, ...] = (0.0, 0.1, 0.25),
) -> dict:
    """Repeat across seeded target/split choices and report rates with 95% intervals."""
    if trials < 1:
        raise ValueError("trials must be >= 1")
    conditions = []
    for attack_index, attack_rate in enumerate(attack_rates):
        rows = [
            run_trial(seed + attack_index * 1_000_003 + i, train_size, attack_rate)
            for i in range(trials)
        ]
        false_accepts = sum(row["false_acceptance"] for row in rows)
        failures = sum(row["heldout_error_clean_labels"] > 0.0 for row in rows)
        exact = sum(row["exact_rule_match"] for row in rows)
        ambiguous = sum(row["ambiguous_minimizers"] for row in rows)
        conditions.append({
            "adversarial_fraction": attack_rate,
            "trials": trials,
            "false_acceptance_rate": false_accepts / trials,
            "false_acceptance_95ci_wilson": wilson_interval(false_accepts, trials),
            "heldout_failure_rate": failures / trials,
            "heldout_failure_95ci_wilson": wilson_interval(failures, trials),
            "exact_rule_match_rate": exact / trials,
            "ambiguous_minimizer_rate": ambiguous / trials,
            "mean_heldout_error": sum(row["heldout_error_clean_labels"] for row in rows) / trials,
            "mean_observed_training_error": sum(row["train_error_observed"] for row in rows) / trials,
        })
    return {
        "benchmark": "phase1c_finite_grammar_heldout_adversarial",
        "seed": seed,
        "domain_size": len(DOMAIN),
        "candidate_count": len(candidate_rules()),
        "trials_per_condition": trials,
        "train_size": train_size,
        "heldout_size": len(DOMAIN) - train_size,
        "confidence_interval": "95% Wilson score interval; binomial approximation",
        "interpretation_limit": (
            "Finite candidate grammar and synthetic binary rules only. "
            "This is not open-ended rule invention, calibrated confidence, "
            "Byzantine consensus, or evidence of intelligence."
        ),
        "conditions": conditions,
    }


def main() -> None:
    print(json.dumps(run_benchmark(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
