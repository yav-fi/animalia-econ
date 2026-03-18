# Simulation Module

This package runs lightweight simulated games from estimated priors.

## Included games
- Public Goods Game
- Ultimatum Game
- Trust Game
- Risk Choice Task

## Default behavior
The CLI is taxon-first and reads `data/processed/animaliaecon_taxon_priors.csv` by default.

```bash
python -m sim.cli public-goods --entity Mammalia --rank class
python -m sim.cli ultimatum --entity Corvidae --rank family
python -m sim.cli trust --entity Hymenoptera --rank order
python -m sim.cli risk-choice --entity Chordata --rank phylum
```

Species mode is optional with an explicit species dataset:

```bash
python -m sim.cli trust \
  --entity "Pan troglodytes" \
  --entity-kind species \
  --dataset data/processed/animaliaecon_species_inherited.csv
```

## Realism benchmark suite
Run simulation sanity/ranking checks:

```bash
make benchmark-sim
```

Output: `data/interim/simulation_benchmark_report.csv`
