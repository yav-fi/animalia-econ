from __future__ import annotations

import random
from dataclasses import dataclass


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass
class SpeciesPriors:
    species: str
    risk_preference: float
    temporal_discount_rate: float
    effort_price_elasticity: float
    cooperation_propensity: float
    inequity_sensitivity: float
    punishment_propensity: float
    tokenization_capacity: float


def public_goods_game(priors: SpeciesPriors, rounds: int = 10, players: int = 5, endowment: float = 10.0, multiplier: float = 1.8) -> dict[str, float]:
    contributions = []
    for _ in range(rounds):
        noise = random.uniform(-0.1, 0.1)
        contribution_rate = _clip01(priors.cooperation_propensity + noise)
        contributions.append(contribution_rate * endowment)

    avg_contribution = sum(contributions) / len(contributions)
    group_return = (avg_contribution * players * multiplier) / players
    return {
        "avg_contribution": round(avg_contribution, 4),
        "expected_payoff": round(endowment - avg_contribution + group_return, 4),
    }


def ultimatum_game(priors: SpeciesPriors, rounds: int = 20, stake: float = 10.0) -> dict[str, float]:
    accepts = 0
    offers = []
    for _ in range(rounds):
        fairness_target = 0.35 + 0.3 * priors.inequity_sensitivity
        offer_frac = _clip01(fairness_target + random.uniform(-0.1, 0.1))
        offers.append(offer_frac * stake)

        min_accept = _clip01(0.15 + 0.45 * priors.inequity_sensitivity)
        if offer_frac >= min_accept:
            accepts += 1

    return {
        "avg_offer": round(sum(offers) / len(offers), 4),
        "acceptance_rate": round(accepts / rounds, 4),
    }


def trust_game(priors: SpeciesPriors, rounds: int = 20, endowment: float = 10.0, multiplier: float = 3.0) -> dict[str, float]:
    sent_values = []
    returned_values = []
    for _ in range(rounds):
        send_frac = _clip01(priors.cooperation_propensity + random.uniform(-0.15, 0.15))
        sent = send_frac * endowment
        received = sent * multiplier

        reciprocity = _clip01((priors.cooperation_propensity + priors.tokenization_capacity) / 2.0)
        returned = received * _clip01(reciprocity + random.uniform(-0.15, 0.15))

        sent_values.append(sent)
        returned_values.append(returned)

    avg_sent = sum(sent_values) / rounds
    avg_returned = sum(returned_values) / rounds
    return {
        "avg_sent": round(avg_sent, 4),
        "avg_returned": round(avg_returned, 4),
        "trust_efficiency": round((avg_returned / max(avg_sent, 1e-6)), 4),
    }


def risk_choice_task(priors: SpeciesPriors, trials: int = 100) -> dict[str, float]:
    risky_choices = 0
    for _ in range(trials):
        # Higher risk_preference and lower temporal_discount_rate increase risky choice rate.
        propensity = 0.25 + 0.35 * (priors.risk_preference / 2.0) + 0.2 * (1.0 - priors.temporal_discount_rate / 2.0)
        if random.random() < _clip01(propensity):
            risky_choices += 1
    return {
        "risky_choice_rate": round(risky_choices / trials, 4),
    }
