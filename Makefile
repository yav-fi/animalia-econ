PYTHON ?= python3
DATASET_VERSION ?= 0.4.0
LAMBDA_FUNCTION ?= AnimaliaEconApi
DEPLOY_REGION ?= us-east-1
DEPLOY_BUCKET ?=
DEPLOY_PREFIX ?= deployments/animaliaeconapi

.PHONY: taxonomy-meta taxonomy-refresh validate-data validate-taxonomy api-schema contract-check pipeline pipeline-ai pipeline-ai-full release-dataset release-dataset-tag prior-history benchmark-sim api-dev deploy-api demo test

taxonomy-meta:
	$(PYTHON) pipeline/fetch_opentree_taxonomy.py --metadata-out data/processed/opentree_release_metadata.json

taxonomy-refresh:
	$(PYTHON) pipeline/fetch_opentree_taxonomy.py --download --extract --metadata-out data/processed/opentree_release_metadata.json
	$(PYTHON) pipeline/build_metazoa_phyla.py --metadata data/processed/opentree_release_metadata.json --out-phyla data/processed/opentree_metazoa_phyla.csv --out-subtree data/interim/opentree/metazoa_subtree_nodes.csv
	MPLCONFIGDIR=/tmp/matplotlib $(PYTHON) pipeline/render_metazoa_tree.py --phyla data/processed/opentree_metazoa_phyla.csv --out docs/assets/metazoa_phyla_snapshot.png
	MPLCONFIGDIR=/tmp/matplotlib $(PYTHON) pipeline/render_metazoa_hierarchy.py --subtree data/interim/opentree/metazoa_subtree_nodes.csv --phyla data/processed/opentree_metazoa_phyla.csv --out docs/assets/metazoa_hierarchy_complex.png
	$(PYTHON) pipeline/validate_processed_outputs.py --mode taxonomy

validate-taxonomy:
	$(PYTHON) pipeline/validate_processed_outputs.py --mode taxonomy

validate-data:
	$(PYTHON) pipeline/validate_processed_outputs.py --mode full

api-schema:
	PYTHONPATH=. $(PYTHON) api/export_v1_schemas.py

contract-check:
	PYTHONPATH=. $(PYTHON) api/export_v1_schemas.py
	git diff --exit-code schema/api/v1

prior-history:
	$(PYTHON) pipeline/build_versioned_priors.py --releases-root releases/datasets --current-taxon data/processed/animaliaecon_taxon_priors.csv --current-species data/processed/animaliaecon_species_observed.csv --out-taxon-history data/processed/animaliaecon_taxon_priors_history.csv --out-species-history data/processed/animaliaecon_species_observed_history.csv --out-drift-detail data/processed/animaliaecon_prior_drift_detail.csv --out-drift-summary data/processed/animaliaecon_prior_drift_summary.csv

pipeline:
	$(PYTHON) pipeline/expand_species_candidates.py --seed data/seeds/species_seed.csv --target-clades data/seeds/target_clades.csv --candidate-bank data/seeds/species_candidate_bank.csv --out-species data/interim/species_expanded.csv --out-coverage data/interim/species_expansion_coverage.csv
	$(PYTHON) pipeline/extract_taxonomy.py --seed data/interim/species_expanded.csv --out data/interim/taxonomy_backbone.csv
	$(PYTHON) pipeline/extract_traits.py --seed data/interim/species_expanded.csv --out data/interim/traits_normalized.csv
	$(PYTHON) pipeline/extract_behavior_literature.py --species data/interim/species_expanded.csv --out data/interim/behavior_evidence.csv
	$(PYTHON) pipeline/quantify_priors_ai.py --species data/interim/species_expanded.csv --traits data/interim/traits_normalized.csv --behavior data/interim/behavior_evidence.csv --out data/interim/priors_estimated.csv
	$(PYTHON) pipeline/fit_hierarchical_model.py --species data/interim/species_expanded.csv --priors data/interim/priors_estimated.csv --out data/interim/priors_posterior.csv --engine auto --diagnostics-out data/interim/bayes_model_diagnostics.csv --ppc-out data/interim/bayes_posterior_predictive_checks.csv
	$(PYTHON) pipeline/calibrate_priors_by_clade.py --species data/interim/species_expanded.csv --priors data/interim/priors_posterior.csv --calibration data/seeds/clade_behavior_calibration.csv --out data/interim/priors_posterior_calibrated.csv --audit-out data/interim/calibration_audit.csv
	$(PYTHON) pipeline/apply_overrides.py --entity-kind species --in data/interim/priors_posterior_calibrated.csv --overrides data/curation/species_overrides.csv --out data/interim/priors_posterior_curated.csv --audit-out data/interim/species_overrides_audit.csv
	$(PYTHON) pipeline/aggregate_taxon_priors.py --species data/interim/species_expanded.csv --priors data/interim/priors_posterior_curated.csv --out data/interim/priors_taxon.csv
	$(PYTHON) pipeline/apply_overrides.py --entity-kind taxon --in data/interim/priors_taxon.csv --overrides data/curation/taxon_overrides.csv --out data/interim/priors_taxon_curated.csv --audit-out data/interim/taxon_overrides_audit.csv
	$(PYTHON) pipeline/build_taxon_dataset.py --taxon-priors data/interim/priors_taxon_curated.csv --out data/processed/animaliaecon_taxon_priors.csv --dataset-version $(DATASET_VERSION)
	$(PYTHON) pipeline/inherit_species_priors.py --species data/interim/species_expanded.csv --taxon-priors data/interim/priors_taxon_curated.csv --out data/processed/animaliaecon_species_inherited.csv
	$(PYTHON) pipeline/build_dataset.py --species data/interim/species_expanded.csv --priors data/interim/priors_posterior_curated.csv --out data/processed/animaliaecon_species_observed.csv --dataset-version $(DATASET_VERSION)
	$(PYTHON) pipeline/build_versioned_priors.py --releases-root releases/datasets --current-taxon data/processed/animaliaecon_taxon_priors.csv --current-species data/processed/animaliaecon_species_observed.csv --out-taxon-history data/processed/animaliaecon_taxon_priors_history.csv --out-species-history data/processed/animaliaecon_species_observed_history.csv --out-drift-detail data/processed/animaliaecon_prior_drift_detail.csv --out-drift-summary data/processed/animaliaecon_prior_drift_summary.csv
	$(PYTHON) pipeline/build_override_queue.py --species-observed data/processed/animaliaecon_species_observed.csv --out data/curation/species_override_review_queue.csv
	$(PYTHON) pipeline/build_evidence_bundles.py --species data/interim/species_expanded.csv --taxonomy data/interim/taxonomy_backbone.csv --behavior data/interim/behavior_evidence.csv --priors-estimated data/interim/priors_estimated.csv --signatures data/interim/priors_estimated_signatures.csv --species-posteriors data/interim/priors_posterior_curated.csv --taxon-priors data/processed/animaliaecon_taxon_priors.csv --calibration-audit data/interim/calibration_audit.csv --out-species data/processed/animaliaecon_evidence_species.csv --out-taxon data/processed/animaliaecon_evidence_taxon.csv
	$(PYTHON) pipeline/validate_processed_outputs.py --mode full
	PYTHONPATH=. $(PYTHON) api/export_v1_schemas.py

pipeline-ai:
	$(PYTHON) pipeline/expand_species_candidates.py --seed data/seeds/species_seed.csv --target-clades data/seeds/target_clades.csv --candidate-bank data/seeds/species_candidate_bank.csv --out-species data/interim/species_expanded.csv --out-coverage data/interim/species_expansion_coverage.csv
	$(PYTHON) pipeline/extract_taxonomy.py --seed data/interim/species_expanded.csv --out data/interim/taxonomy_backbone.csv
	$(PYTHON) pipeline/extract_traits.py --seed data/interim/species_expanded.csv --out data/interim/traits_normalized.csv
	$(PYTHON) pipeline/extract_behavior_literature.py --species data/interim/species_expanded.csv --out data/interim/behavior_evidence.csv
	$(PYTHON) pipeline/quantify_priors_ai.py --species data/interim/species_expanded.csv --traits data/interim/traits_normalized.csv --behavior data/interim/behavior_evidence.csv --out data/interim/priors_estimated.csv --use-ai --update-mode incremental
	$(PYTHON) pipeline/fit_hierarchical_model.py --species data/interim/species_expanded.csv --priors data/interim/priors_estimated.csv --out data/interim/priors_posterior.csv --engine auto --diagnostics-out data/interim/bayes_model_diagnostics.csv --ppc-out data/interim/bayes_posterior_predictive_checks.csv
	$(PYTHON) pipeline/calibrate_priors_by_clade.py --species data/interim/species_expanded.csv --priors data/interim/priors_posterior.csv --calibration data/seeds/clade_behavior_calibration.csv --out data/interim/priors_posterior_calibrated.csv --audit-out data/interim/calibration_audit.csv
	$(PYTHON) pipeline/apply_overrides.py --entity-kind species --in data/interim/priors_posterior_calibrated.csv --overrides data/curation/species_overrides.csv --out data/interim/priors_posterior_curated.csv --audit-out data/interim/species_overrides_audit.csv
	$(PYTHON) pipeline/aggregate_taxon_priors.py --species data/interim/species_expanded.csv --priors data/interim/priors_posterior_curated.csv --out data/interim/priors_taxon.csv
	$(PYTHON) pipeline/apply_overrides.py --entity-kind taxon --in data/interim/priors_taxon.csv --overrides data/curation/taxon_overrides.csv --out data/interim/priors_taxon_curated.csv --audit-out data/interim/taxon_overrides_audit.csv
	$(PYTHON) pipeline/build_taxon_dataset.py --taxon-priors data/interim/priors_taxon_curated.csv --out data/processed/animaliaecon_taxon_priors.csv --dataset-version $(DATASET_VERSION)
	$(PYTHON) pipeline/inherit_species_priors.py --species data/interim/species_expanded.csv --taxon-priors data/interim/priors_taxon_curated.csv --out data/processed/animaliaecon_species_inherited.csv
	$(PYTHON) pipeline/build_dataset.py --species data/interim/species_expanded.csv --priors data/interim/priors_posterior_curated.csv --out data/processed/animaliaecon_species_observed.csv --dataset-version $(DATASET_VERSION)
	$(PYTHON) pipeline/build_versioned_priors.py --releases-root releases/datasets --current-taxon data/processed/animaliaecon_taxon_priors.csv --current-species data/processed/animaliaecon_species_observed.csv --out-taxon-history data/processed/animaliaecon_taxon_priors_history.csv --out-species-history data/processed/animaliaecon_species_observed_history.csv --out-drift-detail data/processed/animaliaecon_prior_drift_detail.csv --out-drift-summary data/processed/animaliaecon_prior_drift_summary.csv
	$(PYTHON) pipeline/build_override_queue.py --species-observed data/processed/animaliaecon_species_observed.csv --out data/curation/species_override_review_queue.csv
	$(PYTHON) pipeline/build_evidence_bundles.py --species data/interim/species_expanded.csv --taxonomy data/interim/taxonomy_backbone.csv --behavior data/interim/behavior_evidence.csv --priors-estimated data/interim/priors_estimated.csv --signatures data/interim/priors_estimated_signatures.csv --species-posteriors data/interim/priors_posterior_curated.csv --taxon-priors data/processed/animaliaecon_taxon_priors.csv --calibration-audit data/interim/calibration_audit.csv --out-species data/processed/animaliaecon_evidence_species.csv --out-taxon data/processed/animaliaecon_evidence_taxon.csv
	$(PYTHON) pipeline/validate_processed_outputs.py --mode full
	PYTHONPATH=. $(PYTHON) api/export_v1_schemas.py

pipeline-ai-full:
	$(PYTHON) pipeline/expand_species_candidates.py --seed data/seeds/species_seed.csv --target-clades data/seeds/target_clades.csv --candidate-bank data/seeds/species_candidate_bank.csv --out-species data/interim/species_expanded.csv --out-coverage data/interim/species_expansion_coverage.csv
	$(PYTHON) pipeline/extract_taxonomy.py --seed data/interim/species_expanded.csv --out data/interim/taxonomy_backbone.csv
	$(PYTHON) pipeline/extract_traits.py --seed data/interim/species_expanded.csv --out data/interim/traits_normalized.csv
	$(PYTHON) pipeline/extract_behavior_literature.py --species data/interim/species_expanded.csv --out data/interim/behavior_evidence.csv
	$(PYTHON) pipeline/quantify_priors_ai.py --species data/interim/species_expanded.csv --traits data/interim/traits_normalized.csv --behavior data/interim/behavior_evidence.csv --out data/interim/priors_estimated.csv --use-ai --update-mode full
	$(PYTHON) pipeline/fit_hierarchical_model.py --species data/interim/species_expanded.csv --priors data/interim/priors_estimated.csv --out data/interim/priors_posterior.csv --engine auto --diagnostics-out data/interim/bayes_model_diagnostics.csv --ppc-out data/interim/bayes_posterior_predictive_checks.csv
	$(PYTHON) pipeline/calibrate_priors_by_clade.py --species data/interim/species_expanded.csv --priors data/interim/priors_posterior.csv --calibration data/seeds/clade_behavior_calibration.csv --out data/interim/priors_posterior_calibrated.csv --audit-out data/interim/calibration_audit.csv
	$(PYTHON) pipeline/apply_overrides.py --entity-kind species --in data/interim/priors_posterior_calibrated.csv --overrides data/curation/species_overrides.csv --out data/interim/priors_posterior_curated.csv --audit-out data/interim/species_overrides_audit.csv
	$(PYTHON) pipeline/aggregate_taxon_priors.py --species data/interim/species_expanded.csv --priors data/interim/priors_posterior_curated.csv --out data/interim/priors_taxon.csv
	$(PYTHON) pipeline/apply_overrides.py --entity-kind taxon --in data/interim/priors_taxon.csv --overrides data/curation/taxon_overrides.csv --out data/interim/priors_taxon_curated.csv --audit-out data/interim/taxon_overrides_audit.csv
	$(PYTHON) pipeline/build_taxon_dataset.py --taxon-priors data/interim/priors_taxon_curated.csv --out data/processed/animaliaecon_taxon_priors.csv --dataset-version $(DATASET_VERSION)
	$(PYTHON) pipeline/inherit_species_priors.py --species data/interim/species_expanded.csv --taxon-priors data/interim/priors_taxon_curated.csv --out data/processed/animaliaecon_species_inherited.csv
	$(PYTHON) pipeline/build_dataset.py --species data/interim/species_expanded.csv --priors data/interim/priors_posterior_curated.csv --out data/processed/animaliaecon_species_observed.csv --dataset-version $(DATASET_VERSION)
	$(PYTHON) pipeline/build_versioned_priors.py --releases-root releases/datasets --current-taxon data/processed/animaliaecon_taxon_priors.csv --current-species data/processed/animaliaecon_species_observed.csv --out-taxon-history data/processed/animaliaecon_taxon_priors_history.csv --out-species-history data/processed/animaliaecon_species_observed_history.csv --out-drift-detail data/processed/animaliaecon_prior_drift_detail.csv --out-drift-summary data/processed/animaliaecon_prior_drift_summary.csv
	$(PYTHON) pipeline/build_override_queue.py --species-observed data/processed/animaliaecon_species_observed.csv --out data/curation/species_override_review_queue.csv
	$(PYTHON) pipeline/build_evidence_bundles.py --species data/interim/species_expanded.csv --taxonomy data/interim/taxonomy_backbone.csv --behavior data/interim/behavior_evidence.csv --priors-estimated data/interim/priors_estimated.csv --signatures data/interim/priors_estimated_signatures.csv --species-posteriors data/interim/priors_posterior_curated.csv --taxon-priors data/processed/animaliaecon_taxon_priors.csv --calibration-audit data/interim/calibration_audit.csv --out-species data/processed/animaliaecon_evidence_species.csv --out-taxon data/processed/animaliaecon_evidence_taxon.csv
	$(PYTHON) pipeline/validate_processed_outputs.py --mode full
	PYTHONPATH=. $(PYTHON) api/export_v1_schemas.py

release-dataset:
	@test -n "$(VERSION)" || (echo "VERSION is required, e.g. make release-dataset VERSION=0.3.0"; exit 1)
	$(MAKE) pipeline-ai PYTHON=$(PYTHON) DATASET_VERSION=$(VERSION)
	$(PYTHON) pipeline/release_dataset.py --version $(VERSION) --notes "$(NOTES)"

release-dataset-tag:
	@test -n "$(VERSION)" || (echo "VERSION is required, e.g. make release-dataset-tag VERSION=0.3.0"; exit 1)
	$(MAKE) pipeline-ai PYTHON=$(PYTHON) DATASET_VERSION=$(VERSION)
	$(PYTHON) pipeline/release_dataset.py --version $(VERSION) --notes "$(NOTES)" --tag

api-dev:
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

deploy-api:
	$(PYTHON) api/deploy_lambda.py --function-name $(LAMBDA_FUNCTION) --region $(DEPLOY_REGION) --s3-prefix $(DEPLOY_PREFIX) $(if $(DEPLOY_BUCKET),--s3-bucket $(DEPLOY_BUCKET),)

demo:
	$(PYTHON) examples/run_demo.py

benchmark-sim:
	$(PYTHON) benchmarks/simulation_realism.py --dataset data/processed/animaliaecon_taxon_priors.csv --out data/interim/simulation_benchmark_report.csv

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v
