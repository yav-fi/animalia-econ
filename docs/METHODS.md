# Methods (Bootstrap)

## Objective
Estimate simulation-ready economic priors with explicit uncertainty, prioritizing higher taxonomic coverage first.

## Parameter set
- risk_preference
- temporal_discount_rate
- effort_price_elasticity
- cooperation_propensity
- inequity_sensitivity
- punishment_propensity
- tokenization_capacity

## Inference approach (current)
1. Refresh OpenTree taxonomy release and anchor on Metazoa/Animalia branch.
2. Build filtered phylum map from the OpenTree subtree while ignoring noisy discrepancy flags (`incertae_sedis`, `unclassified`, `environmental`, `hidden`, etc.).
3. Expand species candidates by target clades and compute per-row confidence scores.
4. Produce deterministic baseline priors at taxon ranks (`family -> order -> class -> phylum`), then waterfall/blend into species rows.
5. Optionally refine estimates with AWS Bedrock models (Claude/Nova) under hard schema bounds.
6. Fit a full Bayesian hierarchy (global -> class -> family -> species) via PyMC NUTS with posterior predictive checks and diagnostics artifacts; use empirical-Bayes only as fallback if PyMC dependencies are unavailable.
7. Calibrate selected clade/parameter posteriors against known behavioral-study anchors.
8. Aggregate to higher taxonomic ranks (`phylum`, `class`, `order`, `family`) as primary release outputs.
9. Optionally inherit back down to species for simulation UX.
10. Emit evidence bundles (species/taxon) with citations, extraction notes, signatures, and AI rationale hashes.
11. Generate a low-confidence review queue so manual edits are confined to `overrides.csv` exceptions.

## Why taxon-first
- Reduces false precision when direct species evidence is sparse.
- Matches the hierarchical-coverage strategy described in the prior-art report.
- Keeps species outputs explicitly marked as inferred/inherited.
- Ensures missing/sparse species inherit coherent clade structure instead of free-floating species-only heuristics.

## Next upgrade path
Move from empirical-Bayes closed-form updates to full probabilistic inference (PyMC/Stan) with explicit study-level likelihoods and posterior predictive checks.
