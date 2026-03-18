from __future__ import annotations

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import fit_hierarchical_model as model


class TestHierarchicalModelTransforms(unittest.TestCase):
    def test_latent_round_trip_across_params(self) -> None:
        samples = {
            "risk_preference": 1.35,
            "temporal_discount_rate": 0.62,
            "effort_price_elasticity": -1.1,
            "cooperation_propensity": 0.74,
            "inequity_sensitivity": 0.31,
            "punishment_propensity": 0.56,
            "tokenization_capacity": 0.67,
        }
        for param, value in samples.items():
            latent = model._to_latent(param, value)
            restored = model._from_latent(param, latent)
            self.assertAlmostEqual(value, restored, places=6, msg=param)

    def test_obs_sd_to_latent_is_positive(self) -> None:
        sd = model._obs_sd_to_latent("cooperation_propensity", 0.5, 0.2)
        self.assertGreater(sd, 0.0)

    def test_diagnostic_fail_reasons(self) -> None:
        diag = {
            "rhat_max": 1.08,
            "ess_bulk_min": 42.0,
            "divergences": 3,
        }
        reasons = model._diagnostic_fail_reasons(
            diag,
            max_rhat=1.01,
            min_ess_bulk=100.0,
            max_divergences=0,
        )
        self.assertEqual(3, len(reasons))
        self.assertTrue(any("rhat_max" in r for r in reasons))
        self.assertTrue(any("ess_bulk_min" in r for r in reasons))
        self.assertTrue(any("divergences" in r for r in reasons))


if __name__ == "__main__":
    unittest.main()
