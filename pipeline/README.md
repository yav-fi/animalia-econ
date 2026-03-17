# Pipeline

## Scripts
- `extract_taxonomy.py`: build canonical taxon table from seed species and taxonomy metadata.
- `extract_traits.py`: normalize trait covariates used for prior estimation.
- `extract_behavior_literature.py`: parse/normalize literature evidence templates.
- `quantify_priors_ai.py`: AI-assisted prior generation with deterministic fallback.
- `fit_hierarchical_model.py`: shrinkage-based taxonomic pooling.
- `build_dataset.py`: produce release dataset for simulations/apps.

## Typical order
1. `extract_taxonomy.py`
2. `extract_traits.py`
3. `extract_behavior_literature.py` (optional at bootstrap)
4. `quantify_priors_ai.py`
5. `fit_hierarchical_model.py`
6. `build_dataset.py`

## Design
The bootstrap avoids heavy dependencies and favors transparent CSV pipelines so you can iterate quickly before switching to larger ETL/model stacks.
