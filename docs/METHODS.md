# Methods (Bootstrap)

## Objective
Estimate simulation-ready priors for animal economic behavior with explicit uncertainty.

## Parameter set
- risk_preference
- temporal_discount_rate
- effort_price_elasticity
- cooperation_propensity
- inequity_sensitivity
- punishment_propensity
- tokenization_capacity

## Inference approach (v0)
1. Use species-level covariates from seed table and normalized traits.
2. Produce baseline priors via deterministic heuristics.
3. Optionally refine with AI estimation from structured evidence.
4. Apply class/family-level shrinkage for stability.
5. Emit posterior-like outputs (`mean`, `lower`, `upper`, `uncertainty_sd`).

## Upgrade path (v1)
Replace shrinkage approximation with hierarchical Bayesian model (PyMC/Stan) and study-level likelihoods.
