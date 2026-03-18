# Data Directory

## Purpose
This folder stores all dataset artifacts from ingestion through release.

## Subfolders
- `raw/`: untouched source dumps and API pulls (gitignored except `.gitkeep`)
- `interim/`: normalized intermediate tables for modeling
- `processed/`: release-ready tables for app/simulation use
- `seeds/`: manually curated seed species and metadata
- `curation/`: manual override files for species/taxon priors

## Core outputs
- `interim/species_expanded.csv`
- `interim/species_expansion_coverage.csv`
- `interim/taxonomy_backbone.csv`
- `interim/traits_normalized.csv`
- `interim/behavior_evidence.csv`
- `interim/priors_estimated.csv`
- `interim/priors_posterior.csv`
- `interim/priors_posterior_calibrated.csv`
- `interim/calibration_audit.csv`
- `interim/bayes_model_diagnostics.csv`
- `interim/bayes_posterior_predictive_checks.csv`
- `interim/priors_taxon.csv`
- `interim/opentree/metazoa_subtree_nodes.csv`
- `processed/opentree_release_metadata.json`
- `processed/animaliaecon_taxon_priors.csv` (primary release)
- `processed/animaliaecon_species_inherited.csv` (optional)
- `processed/animaliaecon_species_observed.csv` (diagnostic/secondary)
- `processed/animaliaecon_evidence_species.csv` (species evidence bundle)
- `processed/animaliaecon_evidence_taxon.csv` (taxon evidence bundle)
- `processed/animaliaecon_taxon_priors_history.csv` (release-indexed taxon history)
- `processed/animaliaecon_species_observed_history.csv` (release-indexed species history)
- `processed/animaliaecon_prior_drift_detail.csv` (per-entity release drift)
- `processed/animaliaecon_prior_drift_summary.csv` (aggregated release drift)
- `processed/opentree_metazoa_phyla.csv`
- `curation/species_override_review_queue.csv` (auto-generated low-confidence review queue)

## Conventions
- Every row should include `taxonomy_source`, `source_version`, and `provenance_type`.
- Distinguish `observed`, `imputed_taxonomy`, `imputed_trait`, and `ai_estimated`.
