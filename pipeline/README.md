# Pipeline

## Scripts
- `fetch_opentree_taxonomy.py`: resolve/download/extract latest OpenTree taxonomy release.
- `build_metazoa_phyla.py`: extract Metazoa subtree and filtered phylum map from OpenTree.
- `render_metazoa_tree.py`: render a README-ready phylum graph snapshot.
- `render_metazoa_hierarchy.py`: render a deeper phylum/class/order hierarchy chart.
- `expand_species_candidates.py`: expand species coverage by target clades and confidence-score each row.
- `extract_taxonomy.py`: build canonical taxon table from seed species and taxonomy metadata.
- `extract_traits.py`: normalize trait covariates used for prior estimation.
- `extract_behavior_literature.py`: parse/normalize literature evidence templates.
  - Auto-scores evidence confidence and emits per-species prior proposal payloads.
- `quantify_priors_ai.py`: AWS Bedrock-assisted prior generation with deterministic fallback.
  - Supports `--update-mode full|incremental` to control recompute behavior and AI spend.
- `fit_hierarchical_model.py`: full Bayesian hierarchy (`PyMC` NUTS) with posterior predictive checks and diagnostics artifacts.
  - `--engine auto` attempts PyMC first and falls back to empirical-Bayes on dependency/runtime failure or failed diagnostics thresholds.
  - PyMC fitting runs in latent (unbounded) space for bounded parameters, then maps posteriors back to the original parameter ranges.
- `calibrate_priors_by_clade.py`: calibrate posterior parameters to clade-level behavioral anchors.
- `apply_overrides.py`: apply manual species/taxon curation overrides with audit logs.
- `aggregate_taxon_priors.py`: aggregate species posteriors to higher taxonomic ranks.
- `build_taxon_dataset.py`: produce release-ready taxon-first dataset.
- `inherit_species_priors.py`: optional species inheritance from higher-rank taxon priors.
- `build_dataset.py`: species-observed release builder.
- `build_override_queue.py`: generate low-confidence exception queue for manual curation via overrides.
- `build_evidence_bundles.py`: generate species/taxon evidence bundles with citations and rationale hashes.
- `build_versioned_priors.py`: build release-indexed prior histories and drift reports.
- `validate_processed_outputs.py`: strict schema/range validation for release artifacts.
- `release_dataset.py`: create versioned snapshots, checksums, changelog entries, and optional git tags.

## Typical order
OpenTree refresh flow:
1. `fetch_opentree_taxonomy.py` (for backbone refresh)
2. `build_metazoa_phyla.py` (for Metazoa phylum mapping)
3. `render_metazoa_tree.py` (for reporting snapshot)
4. `render_metazoa_hierarchy.py` (for deeper hierarchy visualization)

Modeling flow:
1. `expand_species_candidates.py`
2. `extract_taxonomy.py`
3. `extract_traits.py`
4. `extract_behavior_literature.py`
5. `quantify_priors_ai.py`
6. `fit_hierarchical_model.py`
7. `calibrate_priors_by_clade.py`
8. `apply_overrides.py` (species)
9. `aggregate_taxon_priors.py`
10. `apply_overrides.py` (taxon)
11. `build_taxon_dataset.py`
12. `inherit_species_priors.py`
13. `build_dataset.py`
14. `build_override_queue.py`
15. `build_evidence_bundles.py`
16. `build_versioned_priors.py`

## Design
The pipeline is taxon-first: estimate robust higher-rank priors, calibrate to known clade studies, and expose species-level outputs with explicit uncertainty and evidence provenance.
