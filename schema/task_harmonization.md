# Task Harmonization

## Core game families (v1)
- Public Goods Game -> `cooperation_propensity`, `punishment_propensity`
- Ultimatum Game -> `inequity_sensitivity`, `cooperation_propensity`
- Trust Game -> `cooperation_propensity`, `tokenization_capacity`
- Risk Choice Task -> `risk_preference`, `temporal_discount_rate`

## Mapping principles
1. Preserve original study-level units in `economic_params_observed`.
2. Convert to standardized unit interval or bounded scalar in model-ready tables.
3. Track each conversion function and assumptions in provenance fields.
4. Where no direct observation exists, infer with hierarchical taxonomic pooling plus trait covariates.
