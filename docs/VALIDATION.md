# Data Validation

Processed outputs are validated by `pipeline/validate_processed_outputs.py`.

## Modes
- `full`: validates taxon priors, species observed, species inherited, species/taxon evidence bundles, release history + drift artifacts, Bayesian diagnostics/PPC artifacts, OpenTree metadata, and phylum map.
- `taxonomy`: validates OpenTree metadata/phylum outputs and taxon priors.

## Commands
```bash
make validate-data
make validate-taxonomy
```

## Where it runs
- Automatically at the end of:
  - `make pipeline`
  - `make pipeline-ai`
  - `make pipeline-ai-full`
  - `make taxonomy-refresh`
