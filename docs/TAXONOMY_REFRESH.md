# OpenTree Taxonomy Refresh

## Goal
Use OpenTree as the canonical taxonomy backbone for Animalia (Metazoa), then produce a stable phylum map while filtering noisy discrepancies.

## Commands
```bash
# Resolve latest release version only
make taxonomy-meta

# Full refresh (download + extract + map + graph)
make taxonomy-refresh
```

## What `make taxonomy-refresh` does
1. Resolves latest OpenTree release from `https://tree.opentreeoflife.org/about/taxonomy-version`.
2. Downloads `ottX.Y.Z.tgz` from `files.opentreeoflife.org`.
3. Extracts `taxonomy.tsv`, `synonyms.tsv`, and `version.txt`.
4. Builds Metazoa subtree and extracts phylum rows.
5. Filters noisy discrepancy flags (`incertae_sedis`, `unclassified`, `environmental`, `hidden`, `major_rank_conflict`, `extinct_inherited`).
6. Renders `docs/assets/metazoa_phyla_snapshot.png` (phylum overview) for README.
7. Renders `docs/assets/metazoa_hierarchy_complex.png` (phylum->class->order complex chart) for README.

## Update cadence
- Automated monthly refresh via GitHub Actions workflow: `.github/workflows/opentree-taxonomy-refresh.yml`
- Manual refresh anytime via `make taxonomy-refresh`

## Outputs
- `data/processed/opentree_release_metadata.json`
- `data/interim/opentree/metazoa_subtree_nodes.csv`
- `data/processed/opentree_metazoa_phyla.csv`
- `docs/assets/metazoa_phyla_snapshot.png`
- `docs/assets/metazoa_hierarchy_complex.png`

Current value in latest dataset snapshot (`0.6.0`): OpenTree release `ott3.7.3`.
