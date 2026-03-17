PYTHON ?= python3

.PHONY: pipeline demo test

pipeline:
	$(PYTHON) pipeline/extract_taxonomy.py --seed data/seeds/species_seed.csv --out data/interim/taxonomy_backbone.csv
	$(PYTHON) pipeline/extract_traits.py --seed data/seeds/species_seed.csv --out data/interim/traits_normalized.csv
	$(PYTHON) pipeline/extract_behavior_literature.py --species data/seeds/species_seed.csv --out data/interim/behavior_evidence.csv
	$(PYTHON) pipeline/quantify_priors_ai.py --species data/seeds/species_seed.csv --traits data/interim/traits_normalized.csv --out data/interim/priors_estimated.csv
	$(PYTHON) pipeline/fit_hierarchical_model.py --species data/seeds/species_seed.csv --priors data/interim/priors_estimated.csv --out data/interim/priors_posterior.csv
	$(PYTHON) pipeline/build_dataset.py --species data/seeds/species_seed.csv --priors data/interim/priors_posterior.csv --out data/processed/animaliaecon_priors.csv

demo:
	$(PYTHON) examples/run_demo.py

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v
