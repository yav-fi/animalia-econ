from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def to_float(value: str, field: str, row_idx: int, errors: list[str]) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        errors.append(f"row {row_idx}: field `{field}` must be numeric, got `{value}`")
        return None


def validate_against_schema(
    rows: list[dict[str, str]],
    schema: dict,
    dataset_label: str,
    errors: list[str],
) -> None:
    required = schema.get("required", [])
    props = schema.get("properties", {})

    for i, row in enumerate(rows, start=2):
        for field in required:
            if field not in row or str(row[field]).strip() == "":
                errors.append(f"{dataset_label}: row {i} missing required field `{field}`")

        for field, spec in props.items():
            if field not in row:
                continue
            val = row[field]
            if str(val).strip() == "":
                continue

            if spec.get("type") == "number":
                fval = to_float(val, field, i, errors)
                if fval is None:
                    continue
                if "minimum" in spec and fval < float(spec["minimum"]):
                    errors.append(f"{dataset_label}: row {i} field `{field}` below minimum {spec['minimum']}")
                if "maximum" in spec and fval > float(spec["maximum"]):
                    errors.append(f"{dataset_label}: row {i} field `{field}` above maximum {spec['maximum']}")

            if "enum" in spec and val not in spec["enum"]:
                errors.append(f"{dataset_label}: row {i} field `{field}` not in enum {spec['enum']}")

            if "const" in spec and val != spec["const"]:
                errors.append(f"{dataset_label}: row {i} field `{field}` must equal `{spec['const']}`")


def validate_intervals(rows: list[dict[str, str]], params: list[str], dataset_label: str, errors: list[str]) -> None:
    for i, row in enumerate(rows, start=2):
        for p in params:
            if p not in row:
                continue
            lower_k = f"{p}_lower"
            upper_k = f"{p}_upper"
            if lower_k not in row or upper_k not in row:
                continue

            v = to_float(row[p], p, i, errors)
            lo = to_float(row[lower_k], lower_k, i, errors)
            hi = to_float(row[upper_k], upper_k, i, errors)
            if v is None or lo is None or hi is None:
                continue

            if not (lo <= v <= hi):
                errors.append(f"{dataset_label}: row {i} interval violation `{lower_k}` <= `{p}` <= `{upper_k}`")


def validate_metadata(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing metadata file: {path}")
        return

    payload = json.loads(path.read_text(encoding="utf-8"))
    required = ["source", "release_version", "archive_url", "generated_at"]
    for key in required:
        if key not in payload or str(payload[key]).strip() == "":
            errors.append(f"metadata missing required key `{key}`")

    if "release_version" in payload and not str(payload["release_version"]).startswith("ott"):
        errors.append("metadata `release_version` must start with `ott`")


def validate_phyla(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing phyla file: {path}")
        return

    rows = read_csv(path)
    if not rows:
        errors.append("phyla file is empty")
        return

    seen: set[str] = set()
    for i, row in enumerate(rows, start=2):
        name = row.get("phylum_name", "").strip()
        if not name:
            errors.append(f"phyla row {i} missing phylum_name")
            continue
        if name in seen:
            errors.append(f"duplicate phylum_name detected: {name}")
        seen.add(name)


def validate_evidence(path: Path, required: list[str], dataset_label: str, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing evidence dataset: {path}")
        return
    rows = read_csv(path)
    if not rows:
        errors.append(f"empty evidence dataset: {path}")
        return
    for field in required:
        if field not in rows[0]:
            errors.append(f"{dataset_label}: missing required column `{field}`")


def validate_required_file(path: Path, dataset_label: str, required_cols: list[str], errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing required artifact: {path}")
        return
    rows = read_csv(path)
    if not rows:
        errors.append(f"required artifact is empty: {path}")
        return
    for col in required_cols:
        if col not in rows[0]:
            errors.append(f"{dataset_label}: missing required column `{col}`")


def main() -> None:
    parser = argparse.ArgumentParser(description="Strict validation for processed dataset outputs.")
    parser.add_argument("--schema-species", default="schema/economic_param_schema.json")
    parser.add_argument("--schema-taxon", default="schema/taxon_prior_schema.json")
    parser.add_argument("--taxon-priors", default="data/processed/animaliaecon_taxon_priors.csv")
    parser.add_argument("--species-inherited", default="data/processed/animaliaecon_species_inherited.csv")
    parser.add_argument("--species-observed", default="data/processed/animaliaecon_species_observed.csv")
    parser.add_argument("--opentree-meta", default="data/processed/opentree_release_metadata.json")
    parser.add_argument("--opentree-phyla", default="data/processed/opentree_metazoa_phyla.csv")
    parser.add_argument("--evidence-species", default="data/processed/animaliaecon_evidence_species.csv")
    parser.add_argument("--evidence-taxon", default="data/processed/animaliaecon_evidence_taxon.csv")
    parser.add_argument("--taxon-history", default="data/processed/animaliaecon_taxon_priors_history.csv")
    parser.add_argument("--species-history", default="data/processed/animaliaecon_species_observed_history.csv")
    parser.add_argument("--drift-detail", default="data/processed/animaliaecon_prior_drift_detail.csv")
    parser.add_argument("--drift-summary", default="data/processed/animaliaecon_prior_drift_summary.csv")
    parser.add_argument("--bayes-diagnostics", default="data/interim/bayes_model_diagnostics.csv")
    parser.add_argument("--bayes-ppc", default="data/interim/bayes_posterior_predictive_checks.csv")
    parser.add_argument("--mode", choices=["full", "taxonomy"], default="full")
    args = parser.parse_args()

    errors: list[str] = []

    taxon_schema = json.loads(Path(args.schema_taxon).read_text(encoding="utf-8"))
    species_schema = json.loads(Path(args.schema_species).read_text(encoding="utf-8"))

    params = [
        "risk_preference",
        "temporal_discount_rate",
        "effort_price_elasticity",
        "cooperation_propensity",
        "inequity_sensitivity",
        "punishment_propensity",
        "tokenization_capacity",
    ]

    validate_metadata(Path(args.opentree_meta), errors)
    validate_phyla(Path(args.opentree_phyla), errors)

    taxon_rows = read_csv(Path(args.taxon_priors)) if Path(args.taxon_priors).exists() else []
    if not taxon_rows:
        errors.append(f"missing or empty taxon priors: {args.taxon_priors}")
    else:
        validate_against_schema(taxon_rows, taxon_schema, "taxon_priors", errors)
        validate_intervals(taxon_rows, params, "taxon_priors", errors)

    if args.mode == "full":
        for label, path in [
            ("species_inherited", Path(args.species_inherited)),
            ("species_observed", Path(args.species_observed)),
        ]:
            if not path.exists():
                errors.append(f"missing species dataset: {path}")
                continue
            rows = read_csv(path)
            if not rows:
                errors.append(f"empty species dataset: {path}")
                continue
            validate_against_schema(rows, species_schema, label, errors)
            validate_intervals(rows, params, label, errors)

        validate_evidence(
            Path(args.evidence_species),
            required=["entity_kind", "entity_id", "species", "source_citations", "ai_rationale_hash"],
            dataset_label="evidence_species",
            errors=errors,
        )
        validate_evidence(
            Path(args.evidence_taxon),
            required=["entity_kind", "entity_id", "rank", "taxon", "n_species_evidence"],
            dataset_label="evidence_taxon",
            errors=errors,
        )
        validate_required_file(
            Path(args.taxon_history),
            dataset_label="taxon_priors_history",
            required_cols=["release_version", "rank", "taxon", "risk_preference"],
            errors=errors,
        )
        validate_required_file(
            Path(args.species_history),
            dataset_label="species_priors_history",
            required_cols=["release_version", "species", "class", "risk_preference"],
            errors=errors,
        )
        validate_required_file(
            Path(args.drift_detail),
            dataset_label="prior_drift_detail",
            required_cols=["entity_kind", "entity", "param", "from_version", "to_version", "abs_delta"],
            errors=errors,
        )
        validate_required_file(
            Path(args.drift_summary),
            dataset_label="prior_drift_summary",
            required_cols=["entity_kind", "param", "from_version", "to_version", "mean_abs_delta"],
            errors=errors,
        )
        validate_required_file(
            Path(args.bayes_diagnostics),
            dataset_label="bayes_model_diagnostics",
            required_cols=["param", "engine", "ppc_rmse", "ppc_coverage_95"],
            errors=errors,
        )
        validate_required_file(
            Path(args.bayes_ppc),
            dataset_label="bayes_posterior_predictive_checks",
            required_cols=["param", "species", "observed_value", "posterior_mean"],
            errors=errors,
        )

    if errors:
        print("Validation failed:")
        for err in errors:
            print(f"- {err}")
        raise SystemExit(1)

    print("Validation passed.")
    print(f"mode={args.mode}")


if __name__ == "__main__":
    main()
