# Roadmap

## Snapshot (March 19, 2026)
- Completed: repository scaffold, taxonomy refresh automation, taxon-first deterministic baseline, candidate expansion, Bedrock-assisted estimation, evidence bundles, curation overrides, release snapshots, prior histories/drift reports, and read-only `/v1` API contracts.
- Latest shipped artifacts: app tag `v0.5.0` and dataset tag `dataset-v0.6.0` with `306` taxon rows plus `500` species rows.
- In progress: hardening Bayesian diagnostics gates and broadening clade calibration coverage.
- Next focus: expand species coverage without lowering evidence quality, then promote hosted API + simulation UX.

## Phase 0 (foundation) - complete
- Scaffold repository and schema
- Seed species + deterministic extraction baseline
- OpenTree Metazoa refresh automation and hierarchy snapshots

## Phase 1 (pipeline breadth) - complete
- Candidate expansion by target clades with confidence scoring
- AWS Bedrock-assisted prior estimation with deterministic fallback
- Species/taxon evidence bundle generation
- Reproducible taxon-prior release artifacts

## Phase 2 (inference rigor) - active
- Full probabilistic Bayesian model in pipeline (PyMC NUTS path with fallback engine)
- Calibration and posterior predictive checks integrated
- Ongoing work: richer study-level likelihoods and stricter diagnostics thresholds

## Phase 3 (productization) - active
- Continuous dataset updates and release cadence
- Public API and hosted simulation environment
- Drift alerting and release quality dashboards
