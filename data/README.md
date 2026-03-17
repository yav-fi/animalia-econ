# Data Directory

## Purpose
This folder stores all dataset artifacts from ingestion through release.

## Subfolders
- `raw/`: untouched source dumps and API pulls (gitignored except `.gitkeep`)
- `interim/`: normalized intermediate tables for modeling
- `processed/`: release-ready tables for app/simulation use
- `seeds/`: manually curated seed species and metadata

## Core outputs
- `interim/taxonomy_backbone.csv`
- `interim/traits_normalized.csv`
- `interim/priors_estimated.csv`
- `processed/animaliaecon_priors.csv`

## Conventions
- Every row should include `taxonomy_source`, `source_version`, and `provenance_type`.
- Distinguish `observed`, `imputed_taxonomy`, `imputed_trait`, and `ai_estimated`.
