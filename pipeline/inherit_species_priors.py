from __future__ import annotations

import argparse

from common import ProgressPrinter, clamp, read_csv, write_csv

PARAMS = [
    "risk_preference",
    "temporal_discount_rate",
    "effort_price_elasticity",
    "cooperation_propensity",
    "inequity_sensitivity",
    "punishment_propensity",
    "tokenization_capacity",
]

RANK_BACKOFF = ["family", "order", "class", "phylum"]


def _bounds(param: str) -> tuple[float, float]:
    if param == "effort_price_elasticity":
        return -3.0, 1.0
    if param in {"risk_preference", "temporal_discount_rate"}:
        return 0.0, 2.0
    return 0.0, 1.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Create optional species priors by inheriting from higher-rank taxon priors.")
    parser.add_argument("--species", required=True, help="Species seed CSV.")
    parser.add_argument("--taxon-priors", required=True, help="Taxon priors CSV.")
    parser.add_argument("--out", required=True, help="Output CSV for inherited species priors.")
    args = parser.parse_args()

    species_rows = read_csv(args.species)
    taxon_rows = read_csv(args.taxon_priors)

    taxon_lookup: dict[tuple[str, str], dict[str, str]] = {}
    for row in taxon_rows:
        key = (row.get("rank", "").strip(), row.get("taxon", "").strip())
        if key[0] and key[1]:
            taxon_lookup[key] = row

    out_rows: list[dict[str, object]] = []
    progress = ProgressPrinter(total=len(species_rows), label="inherit_species")
    for sp in species_rows:
        source = None
        source_rank = ""
        source_taxon = ""

        for rank in RANK_BACKOFF:
            taxon_name = sp.get(rank, "").strip()
            candidate = taxon_lookup.get((rank, taxon_name))
            if candidate:
                source = candidate
                source_rank = rank
                source_taxon = taxon_name
                break

        if not source:
            progress.tick()
            continue

        base_sd = float(source["uncertainty_sd"])
        inherited_sd = round(clamp(base_sd + 0.05, 0.01, 1.0), 6)
        row: dict[str, object] = {
            "species": sp["species"],
            "common_name": sp["common_name"],
            "kingdom": sp["kingdom"],
            "phylum": sp["phylum"],
            "class": sp["class"],
            "order": sp["order"],
            "family": sp["family"],
            "genus": sp["genus"],
            "is_seed": sp.get("is_seed", ""),
            "candidate_source": sp.get("candidate_source", ""),
            "candidate_confidence_score": sp.get("candidate_confidence_score", ""),
            "inherited_from_rank": source_rank,
            "inherited_from_taxon": source_taxon,
            "uncertainty_sd": inherited_sd,
            "provenance_type": "inherited_taxonomy",
            "source_model": source.get("source_model", "taxon_aggregate_v0"),
            "calibration_applied": source.get("calibration_applied", "false"),
            "calibration_refs": source.get("calibration_refs", ""),
        }

        for p in PARAMS:
            low, high = _bounds(p)
            value = clamp(float(source[p]), low, high)
            lower = clamp(value - 1.96 * inherited_sd, low, high)
            upper = clamp(value + 1.96 * inherited_sd, low, high)
            row[p] = round(value, 6)
            row[f"{p}_lower"] = round(lower, 6)
            row[f"{p}_upper"] = round(upper, 6)

        out_rows.append(row)
        progress.tick()
    progress.finish()

    if not out_rows:
        raise SystemExit("No inherited rows generated. Check taxonomy overlap.")

    fields = [
        "species",
        "common_name",
        "kingdom",
        "phylum",
        "class",
        "order",
        "family",
        "genus",
        "is_seed",
        "candidate_source",
        "candidate_confidence_score",
        "inherited_from_rank",
        "inherited_from_taxon",
        *PARAMS,
        *[f"{p}_lower" for p in PARAMS],
        *[f"{p}_upper" for p in PARAMS],
        "uncertainty_sd",
        "provenance_type",
        "source_model",
        "calibration_applied",
        "calibration_refs",
    ]
    write_csv(args.out, out_rows, fields)
    print(f"Wrote inherited species priors: {len(out_rows)} -> {args.out}")


if __name__ == "__main__":
    main()
