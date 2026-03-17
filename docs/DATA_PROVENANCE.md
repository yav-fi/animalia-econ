# Data Provenance Policy

## Required provenance fields
- `source_name`
- `source_version`
- `retrieved_at`
- `provenance_type`
- `transformation_id`

## Provenance types
- `observed`: directly measured in a study or curated dataset
- `imputed_taxonomy`: inferred through taxonomic pooling
- `imputed_trait`: inferred from trait covariates
- `ai_estimated`: estimated by AI from structured evidence + constraints

## Rule
No released value should exist without a provenance record and uncertainty estimate.
