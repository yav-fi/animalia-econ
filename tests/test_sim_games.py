from __future__ import annotations

import unittest

from sim.games import SpeciesPriors, public_goods_game, risk_choice_task, trust_game, ultimatum_game


def _priors() -> SpeciesPriors:
    return SpeciesPriors(
        species="Test species",
        risk_preference=1.0,
        temporal_discount_rate=0.6,
        effort_price_elasticity=-0.7,
        cooperation_propensity=0.7,
        inequity_sensitivity=0.6,
        punishment_propensity=0.5,
        tokenization_capacity=0.65,
    )


class TestSimGames(unittest.TestCase):
    def test_public_goods_outputs(self) -> None:
        out = public_goods_game(_priors(), rounds=5)
        self.assertIn("avg_contribution", out)
        self.assertIn("expected_payoff", out)

    def test_ultimatum_outputs(self) -> None:
        out = ultimatum_game(_priors(), rounds=5)
        self.assertGreaterEqual(out["acceptance_rate"], 0.0)
        self.assertLessEqual(out["acceptance_rate"], 1.0)

    def test_trust_outputs(self) -> None:
        out = trust_game(_priors(), rounds=5)
        self.assertGreaterEqual(out["avg_sent"], 0.0)

    def test_risk_choice_outputs(self) -> None:
        out = risk_choice_task(_priors(), trials=10)
        self.assertGreaterEqual(out["risky_choice_rate"], 0.0)
        self.assertLessEqual(out["risky_choice_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
