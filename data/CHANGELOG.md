# Dataset Changelog

## 0.0.0-initial - 2026-03-17

- Bootstrap baseline before formal snapshot flow.
## 0.3.0 - 2026-03-17

Introduce curation overrides, API service, and release automation

Files:
- `data/processed/animaliaecon_taxon_priors.csv` (147adf260b96..., 11585 bytes)
- `data/processed/animaliaecon_species_inherited.csv` (5da6fd1ba922..., 7151 bytes)
- `data/processed/animaliaecon_species_observed.csv` (b176b77a4fb8..., 7596 bytes)
- `data/processed/opentree_metazoa_phyla.csv` (95b303856927..., 2674 bytes)
- `data/processed/opentree_release_metadata.json` (8dbd23dfdc74..., 596 bytes)
- `docs/assets/metazoa_phyla_snapshot.png` (df011d1fd3a6..., 216413 bytes)
- `docs/assets/metazoa_hierarchy_complex.png` (d1cc602b2862..., 1038457 bytes)
## 0.3.1 - 2026-03-17

Auth/rate-limit observability + CI + API contract policy

Files:
- `data/processed/animaliaecon_taxon_priors.csv` (4cedbe431252..., 11585 bytes)
- `data/processed/animaliaecon_species_inherited.csv` (5da6fd1ba922..., 7151 bytes)
- `data/processed/animaliaecon_species_observed.csv` (a2021b5f20d5..., 7596 bytes)
- `data/processed/opentree_metazoa_phyla.csv` (95b303856927..., 2674 bytes)
- `data/processed/opentree_release_metadata.json` (8dbd23dfdc74..., 596 bytes)
- `schema/api/v1/index.json` (8043d640bd05..., 281 bytes)
- `schema/api/v1/contract.response.json` (8aeec6d6cd59..., 492 bytes)
- `schema/api/v1/meta.response.json` (3b3ce571f3c3..., 1047 bytes)
- `schema/api/v1/taxon_priors.response.json` (21924cc7a214..., 382 bytes)
- `schema/api/v1/simulate.request.json` (ecdeeddfcfb1..., 1424 bytes)
- `schema/api/v1/simulate.response.json` (b28f918d689b..., 510 bytes)
- `docs/assets/metazoa_phyla_snapshot.png` (df011d1fd3a6..., 216413 bytes)
- `docs/assets/metazoa_hierarchy_complex.png` (d1cc602b2862..., 1038457 bytes)
## 0.4.0 - 2026-03-18

Release candidate snapshot using reparameterized PyMC posteriors and diagnostics-gated auto fallback.

Files:
- `data/processed/animaliaecon_taxon_priors.csv` (757ccf7baa70..., 26402 bytes)
- `data/processed/animaliaecon_species_inherited.csv` (6002498a1abe..., 20320 bytes)
- `data/processed/animaliaecon_species_observed.csv` (e9c778dc6ee5..., 35623 bytes)
- `data/processed/animaliaecon_evidence_species.csv` (1426d4d13a5c..., 28505 bytes)
- `data/processed/animaliaecon_evidence_taxon.csv` (e81cc73ae46d..., 35075 bytes)
- `data/processed/opentree_metazoa_phyla.csv` (95b303856927..., 2674 bytes)
- `data/processed/opentree_release_metadata.json` (8dbd23dfdc74..., 596 bytes)
- `schema/api/v1/index.json` (4ec552e6ae3f..., 419 bytes)
- `schema/api/v1/contract.response.json` (8aeec6d6cd59..., 492 bytes)
- `schema/api/v1/meta.response.json` (aa65b03ffc69..., 1382 bytes)
- `schema/api/v1/taxon_priors.response.json` (21924cc7a214..., 382 bytes)
- `schema/api/v1/simulate.request.json` (a548ca22113a..., 1631 bytes)
- `schema/api/v1/simulate.response.json` (b28f918d689b..., 510 bytes)
- `docs/assets/metazoa_phyla_snapshot.png` (df011d1fd3a6..., 216413 bytes)
- `docs/assets/metazoa_hierarchy_complex.png` (d1cc602b2862..., 1038457 bytes)
## 0.5.0 - 2026-03-19

Added new species coverage; fixed AI pipeline model defaults, Bedrock error handling, and prompt keying

Files:
- `data/processed/animaliaecon_taxon_priors.csv` (16885c95a328..., 45213 bytes)
- `data/processed/animaliaecon_species_inherited.csv` (154e7a8045b8..., 44826 bytes)
- `data/processed/animaliaecon_species_observed.csv` (25a2e7f5b93e..., 79411 bytes)
- `data/processed/animaliaecon_evidence_species.csv` (25dcd5386a05..., 67334 bytes)
- `data/processed/animaliaecon_evidence_taxon.csv` (f52ebb0a9a31..., 90687 bytes)
- `data/processed/opentree_metazoa_phyla.csv` (95b303856927..., 2674 bytes)
- `data/processed/opentree_release_metadata.json` (8dbd23dfdc74..., 596 bytes)
- `schema/api/v1/index.json` (4ec552e6ae3f..., 419 bytes)
- `schema/api/v1/contract.response.json` (8aeec6d6cd59..., 492 bytes)
- `schema/api/v1/meta.response.json` (aa65b03ffc69..., 1382 bytes)
- `schema/api/v1/taxon_priors.response.json` (21924cc7a214..., 382 bytes)
- `schema/api/v1/simulate.request.json` (a548ca22113a..., 1631 bytes)
- `schema/api/v1/simulate.response.json` (b28f918d689b..., 510 bytes)
- `docs/assets/metazoa_phyla_snapshot.png` (df011d1fd3a6..., 216413 bytes)
- `docs/assets/metazoa_hierarchy_complex.png` (d1cc602b2862..., 1038457 bytes)
## 0.6.0 - 2026-03-19

Release 0.6.0

Files:
- `data/processed/animaliaecon_taxon_priors.csv` (aec9372e39f0..., 113244 bytes)
- `data/processed/animaliaecon_species_inherited.csv` (6e5bb487c66a..., 236047 bytes)
- `data/processed/animaliaecon_species_observed.csv` (f8b6d95b397a..., 412703 bytes)
- `data/processed/animaliaecon_evidence_species.csv` (a1f8cde142aa..., 371205 bytes)
- `data/processed/animaliaecon_evidence_taxon.csv` (84a83fd1d7f3..., 482753 bytes)
- `data/processed/opentree_metazoa_phyla.csv` (95b303856927..., 2674 bytes)
- `data/processed/opentree_release_metadata.json` (8dbd23dfdc74..., 596 bytes)
- `schema/api/v1/index.json` (4ec552e6ae3f..., 419 bytes)
- `schema/api/v1/contract.response.json` (8aeec6d6cd59..., 492 bytes)
- `schema/api/v1/meta.response.json` (aa65b03ffc69..., 1382 bytes)
- `schema/api/v1/taxon_priors.response.json` (21924cc7a214..., 382 bytes)
- `schema/api/v1/simulate.request.json` (a548ca22113a..., 1631 bytes)
- `schema/api/v1/simulate.response.json` (b28f918d689b..., 510 bytes)
- `docs/assets/metazoa_phyla_snapshot.png` (df011d1fd3a6..., 216413 bytes)
- `docs/assets/metazoa_hierarchy_complex.png` (d1cc602b2862..., 1038457 bytes)
