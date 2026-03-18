# Manual Curation Overrides

Use these CSVs to apply domain overrides on top of modeled priors.

## Files
- `species_overrides.csv`: overrides for species-level posterior rows
- `taxon_overrides.csv`: overrides for taxon-level aggregated rows
- `species_override_review_queue.csv`: auto-generated low-confidence/high-uncertainty queue to guide exception-only manual edits

## Supported params
- `risk_preference`
- `temporal_discount_rate`
- `effort_price_elasticity`
- `cooperation_propensity`
- `inequity_sensitivity`
- `punishment_propensity`
- `tokenization_capacity`
- `uncertainty_sd`
- `provenance_type`
- `source_model`

## Rules
- Set `active=true` to apply an override.
- For numeric params, bounds are enforced.
- If a numeric parameter changes, its lower/upper CI fields are recomputed using current `uncertainty_sd`.
- If `uncertainty_sd` changes, all CI fields are recomputed.
