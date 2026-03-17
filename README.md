# animalia-econ

AnimaliaEcon is an open, machine-readable dataset and reproducible pipeline for estimating economic-game parameter priors across animal taxa.

The project starts with four simulation-ready game families:
- Public Goods Game (cooperation/contribution)
- Ultimatum Game (fairness/inequity sensitivity)
- Trust Game (reciprocal exchange)
- Risk Choice Task (risk tolerance)

## What this repository contains
- Taxonomy + trait ingestion scaffolding
- AI-assisted prior quantification pipeline
- Uncertainty-aware prior outputs per taxon/species
- Simulation tools to test species priors in the four core games

## Animalia Labs
Explore interactive demos and future hosted tools at [AnimaliaLabs.com](https://animalialabs.com). The goal there is to let users query taxa, inspect priors, and run game simulations in-browser.

## Quickstart
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python pipeline/extract_taxonomy.py --seed data/seeds/species_seed.csv --out data/interim/taxonomy_backbone.csv
python pipeline/extract_traits.py --seed data/seeds/species_seed.csv --out data/interim/traits_normalized.csv
python pipeline/quantify_priors_ai.py \
  --species data/seeds/species_seed.csv \
  --traits data/interim/traits_normalized.csv \
  --out data/interim/priors_estimated.csv
python pipeline/fit_hierarchical_model.py \
  --species data/seeds/species_seed.csv \
  --priors data/interim/priors_estimated.csv \
  --out data/interim/priors_posterior.csv
python pipeline/build_dataset.py \
  --species data/seeds/species_seed.csv \
  --priors data/interim/priors_posterior.csv \
  --out data/processed/animaliaecon_priors.csv

python -m sim.cli risk-choice --species "Pan troglodytes"
python -m sim.cli public-goods --species "Corvus corax"
```

## Repository layout
- `data/`: raw/interim/processed assets and seed species list
- `schema/`: parameter schema and task harmonization spec
- `pipeline/`: ingestion, extraction, and prior estimation scripts
- `sim/`: simulation engine and CLI for the four games
- `examples/`: runnable examples
- `docs/`: methods, provenance, limitations, roadmap
- `prompts/`: AI extraction and prior quantification prompts

## Current status
This is a bootstrap scaffold with mocked data connectors and deterministic fallbacks. It is intended to make v0 -> v1 implementation fast while keeping provenance and uncertainty first-class.

## License
- Code: MIT License  
- Dataset: CC BY 4.0 (see [DATA_LICENSE.md](/DATALICENSE.md))