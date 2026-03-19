# Seed Inputs And Wishlist

This folder controls how species enter modeling.

## Files
- `species_seed.csv`: baseline species set included every run.
- `species_candidate_bank.csv`: wishlist/candidate pool used to fill clade targets.
- `target_clades.csv`: target coverage by rank/taxon (`target_n`).
- `clade_behavior_calibration.csv`: calibration anchors used after Bayesian pooling.

## How expansion works
`pipeline/expand_species_candidates.py` does three things:
1. Starts from all rows in `species_seed.csv`.
2. For each `target_clades.csv` row where `rank=class`, checks current count in that class.
3. Pulls highest-priority rows from `species_candidate_bank.csv` until `target_n` is met.

Priority is based on `source_confidence` (`high > medium > low`), then species name.
Rows are deduplicated by `species`.

## Where to add more animals
Add new wishlist animals to `species_candidate_bank.csv`.

Use `species_seed.csv` only when you want a species to be permanently part of the baseline set.

If you want to expand cohort sizes, increase `target_n` in `target_clades.csv`.

## Row checklist for `species_candidate_bank.csv`
- Keep the existing header exactly.
- Provide taxonomy fields through at least `class` and ideally to `genus`.
- Fill trait/context fields when available:
  - `body_mass_kg`
  - `sociality_score`
  - `diet_breadth_score`
  - `activity_pattern`
  - `habitat_type`
- Set `source_confidence` to `high`, `medium`, or `low`.
- Set `candidate_source` and `source_citation` to auditable references.

## Verify after edits
Run:

```bash
make pipeline
```

Then inspect:
- `data/interim/species_expansion_coverage.csv` for class coverage/shortfall.
- `data/interim/species_expanded.csv` to confirm your new rows were selected.
