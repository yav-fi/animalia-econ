# Dataset Release Flow

## Goal
Create repeatable, versioned dataset snapshots with checksums and changelog.

## Commands
```bash
# Snapshot only
make release-dataset VERSION=0.3.0 NOTES="Taxon prior refresh"

# Snapshot + git tag
make release-dataset-tag VERSION=0.3.0 NOTES="Taxon prior refresh"
```

## What it does
- Copies release files into `releases/datasets/<version>/`
- Writes `manifest.json`
- Writes `checksums.sha256`
- Appends entry to `data/CHANGELOG.md`
- Optionally creates git tag `dataset-v<version>`
- These snapshots are consumable directly via API dataset pinning (`?dataset_version=<version>`) and `/v1/snapshots/{version}/...` endpoints.

## Primary release files
- `data/processed/animaliaecon_taxon_priors.csv`
- `data/processed/animaliaecon_species_inherited.csv`
- `data/processed/animaliaecon_species_observed.csv`
- `data/processed/animaliaecon_evidence_species.csv`
- `data/processed/animaliaecon_evidence_taxon.csv`
- `data/processed/opentree_metazoa_phyla.csv`
- `data/processed/opentree_release_metadata.json`
- `schema/api/v1/*.json` contract snapshots
- `docs/assets/metazoa_phyla_snapshot.png`
- `docs/assets/metazoa_hierarchy_complex.png`

## Drift tracking
`make pipeline*` also emits:
- `data/processed/animaliaecon_taxon_priors_history.csv`
- `data/processed/animaliaecon_species_observed_history.csv`
- `data/processed/animaliaecon_prior_drift_detail.csv`
- `data/processed/animaliaecon_prior_drift_summary.csv`
