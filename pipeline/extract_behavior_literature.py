from __future__ import annotations

import argparse
import json
import math

from common import ProgressPrinter, clamp, read_csv, write_csv


def _source_confidence_score(value: str) -> float:
    key = (value or "").strip().lower()
    return {"high": 0.9, "medium": 0.75, "low": 0.6}.get(key, 0.55)


def _task_profile(taxon_class: str) -> tuple[str, str, float]:
    if taxon_class == "Mammalia":
        return (
            "trust,ultimatum,public-goods",
            "Mammal clade profile: social exchange and fairness paradigms prioritized.",
            0.84,
        )
    if taxon_class == "Aves":
        return (
            "public-goods,risk-choice,trust",
            "Avian clade profile: cooperation and uncertainty-sensitive foraging paradigms prioritized.",
            0.8,
        )
    if taxon_class == "Insecta":
        return (
            "public-goods,risk-choice",
            "Insect clade profile: collective action and foraging-risk paradigms prioritized.",
            0.73,
        )
    if taxon_class in {"Actinopterygii", "Chondrichthyes"}:
        return (
            "risk-choice,trust",
            "Fish clade profile: risk-choice and reciprocal exchange proxies prioritized.",
            0.74,
        )
    return (
        "risk-choice",
        "General clade profile: sparse direct evidence; generic risk-choice template applied.",
        0.58,
    )


def _is_seed(value: str) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


def _safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _propose_prior_shift(row: dict[str, str], tasks: list[str], evidence_confidence: float) -> dict[str, float]:
    social = clamp(_safe_float(row.get("sociality_score", ""), 0.5), 0.0, 1.0)
    mass_kg = max(_safe_float(row.get("body_mass_kg", ""), 1.0), 0.001)
    mass_log_scaled = clamp(math.log10(1.0 + mass_kg) / 3.0, 0.0, 1.0)
    scale = clamp(evidence_confidence, 0.0, 1.0)

    shift = {
        "risk_preference": 0.0,
        "temporal_discount_rate": 0.0,
        "effort_price_elasticity": 0.0,
        "cooperation_propensity": 0.0,
        "inequity_sensitivity": 0.0,
        "punishment_propensity": 0.0,
        "tokenization_capacity": 0.0,
    }

    if "public-goods" in tasks:
        shift["cooperation_propensity"] += 0.045 * scale
        shift["punishment_propensity"] += 0.02 * scale
    if "ultimatum" in tasks:
        shift["inequity_sensitivity"] += 0.04 * scale
        shift["punishment_propensity"] += 0.015 * scale
    if "trust" in tasks:
        shift["cooperation_propensity"] += 0.03 * scale
        shift["tokenization_capacity"] += 0.02 * scale
    if "risk-choice" in tasks:
        shift["risk_preference"] += 0.08 * (0.5 - social) * scale
        shift["temporal_discount_rate"] += 0.06 * (0.5 - mass_log_scaled) * scale

    return {k: round(v, 6) for k, v in shift.items()}


def build_templates(species_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    progress = ProgressPrinter(total=len(species_rows), label="extract_behavior")
    for row in species_rows:
        taxon_class = row.get("class", "").strip()
        task_family, evidence_text, class_base = _task_profile(taxon_class)
        tasks = [t.strip() for t in task_family.split(",") if t.strip()]

        source_conf = _source_confidence_score(row.get("source_confidence", ""))
        candidate_conf = clamp(_safe_float(row.get("candidate_confidence_score", ""), 0.65), 0.0, 1.0)
        seed_bonus = 0.05 if _is_seed(row.get("is_seed", "")) else 0.0
        evidence_confidence = clamp(0.4 * source_conf + 0.35 * candidate_conf + 0.25 * class_base + seed_bonus, 0.0, 1.0)

        prior_shift = _propose_prior_shift(row, tasks, evidence_confidence)

        rows.append(
            {
                "species": row["species"],
                "task_family": task_family,
                "evidence_text": evidence_text,
                "evidence_confidence": round(evidence_confidence, 6),
                "source_name": "auto_clade_profile_v2",
                "evidence_method": "taxonomy_trait_heuristic",
                "prior_proposal_json": json.dumps(prior_shift, sort_keys=True, separators=(",", ":")),
            }
        )
        progress.tick()
    progress.finish()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Create behavior-literature extraction templates.")
    parser.add_argument("--species", required=True, help="Path to seed species CSV.")
    parser.add_argument("--out", required=True, help="Output CSV path.")
    args = parser.parse_args()

    species_rows = read_csv(args.species)
    rows = build_templates(species_rows)
    fields = [
        "species",
        "task_family",
        "evidence_text",
        "evidence_confidence",
        "source_name",
        "evidence_method",
        "prior_proposal_json",
    ]
    write_csv(args.out, rows, fields)
    print(f"Wrote behavior templates: {len(rows)} -> {args.out}")


if __name__ == "__main__":
    main()
