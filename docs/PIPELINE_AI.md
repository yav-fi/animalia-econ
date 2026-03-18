# `make pipeline-ai` Explained

`make pipeline-ai` runs the same base pipeline as `make pipeline`, but enables AWS Bedrock refinement during prior estimation with incremental compute reuse.

## Recompute mode tag
- `make pipeline-ai` uses `--update-mode incremental` (reuse unchanged species rows).
- `make pipeline-ai-full` uses `--update-mode full` (force full recompute).

Incremental mode uses per-species signatures stored in `data/interim/priors_estimated_signatures.csv`.
If taxonomy/traits/model/prompt version changed, that species is recalculated.
Signatures also include deterministic taxon-anchor context, so species sharing a changed anchor are recalculated together.

## Steps executed
1. `expand_species_candidates.py`
2. `extract_taxonomy.py`
3. `extract_traits.py`
4. `extract_behavior_literature.py`
5. `quantify_priors_ai.py --use-ai --update-mode incremental` (or `full`)
6. `fit_hierarchical_model.py --engine auto` (PyMC full Bayesian when available; auto-fallback to empirical-Bayes on runtime failure or poor diagnostics thresholds)
7. `calibrate_priors_by_clade.py` (study-anchored clade calibration)
8. `apply_overrides.py` (species)
9. `aggregate_taxon_priors.py`
10. `apply_overrides.py` (taxon)
11. `build_taxon_dataset.py`
12. `inherit_species_priors.py`
13. `build_dataset.py` (species-observed secondary output)
14. `build_override_queue.py` (manual exception queue)
15. `build_evidence_bundles.py`
16. `build_versioned_priors.py` (history + drift across releases)

## Prompt and inputs
Prompt construction lives in `pipeline/quantify_priors_ai.py` (`build_prompt`).

Per species, the model gets:
- Taxonomy fields: phylum, class, order, family
- Normalized traits: mass_scaled, sociality_score, diet_breadth_score, activity_score, habitat_complexity_score
- Deterministic taxon-waterfall anchor prior (nearest of family/order/class/phylum)
- Auto-extracted behavior evidence profile (`task_family`, confidence, prior proposal payload)
- Hard value bounds for all parameters

System instruction requires strict JSON output with:
- risk_preference
- temporal_discount_rate
- effort_price_elasticity
- cooperation_propensity
- inequity_sensitivity
- punishment_propensity
- tokenization_capacity
- uncertainty_sd

## Bedrock model call
`quantify_priors_ai.py` uses Bedrock `converse` API with:
- `BEDROCK_MODEL_ID` (default Claude Sonnet model ID)
- `AWS_REGION`
- low-temperature settings for stable numeric output
- explicit timeout config (`connect_timeout=8`, `read_timeout=35`)
- retry/backoff controls:
  - `--ai-max-retries` (default `2`)
  - `--ai-base-backoff-seconds` (default `1.0`)

If Bedrock call fails or returns invalid JSON, the script falls back to deterministic priors.
Per-species failures are logged to `data/interim/priors_estimated_ai_errors.csv` (or `--error-log` path).

## Output meaning
### `data/interim/priors_estimated.csv`
Per-species estimated priors before hierarchical pooling.
- `provenance_type=ai_estimated` when Bedrock response is valid
- `provenance_type=imputed_trait` when deterministic fallback is used

### `data/interim/priors_estimated_signatures.csv`
Per-species signature cache used by incremental mode.
- `action=reused` means no recompute was needed
- `action=recalculated` means this row was recomputed

### `data/interim/priors_posterior.csv`
Species priors after hierarchical pooling with parameter-level posterior uncertainty.

### `data/interim/bayes_model_diagnostics.csv`
Model diagnostics by parameter (`engine`, `rhat`, `ess`, divergences, PPC summary metrics).
- `engine=empirical_bayes_fallback` indicates `--engine auto` switched from PyMC to empirical-Bayes for that parameter after diagnostics gating.

### `data/interim/bayes_posterior_predictive_checks.csv`
Posterior predictive check rows by parameter and species.

### `data/interim/priors_posterior_calibrated.csv`
Species priors after clade-level calibration against known behavioral anchors.

### `data/interim/calibration_audit.csv`
Audit trail of all calibration operations (rank/taxon/parameter/weight/adjustment/citation).

### `data/processed/animaliaecon_taxon_priors.csv`
Primary release output: phylum/class/order/family priors with uncertainty.

### `data/processed/animaliaecon_species_inherited.csv`
Optional species priors inherited from nearest available taxon rank.

### `data/processed/animaliaecon_evidence_species.csv`
Species evidence bundle with citations, extraction notes, signatures, and AI rationale hashes.

### `data/processed/animaliaecon_evidence_taxon.csv`
Taxon evidence bundle aggregated from member-species evidence.

### `data/curation/species_override_review_queue.csv`
Low-confidence/high-uncertainty queue to drive manual edits only through `species_overrides.csv`.

### `data/processed/animaliaecon_taxon_priors_history.csv`
Release-indexed history table for taxon priors.

### `data/processed/animaliaecon_species_observed_history.csv`
Release-indexed history table for species-observed priors.

### `data/processed/animaliaecon_prior_drift_detail.csv`
Per-entity, per-parameter drift between successive releases.

### `data/processed/animaliaecon_prior_drift_summary.csv`
Aggregated drift metrics by release transition and parameter.
