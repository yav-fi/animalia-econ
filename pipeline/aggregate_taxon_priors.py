from __future__ import annotations

import argparse
import math
from collections import defaultdict

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


def _bounds(param: str) -> tuple[float, float]:
    if param == "effort_price_elasticity":
        return -3.0, 1.0
    if param in {"risk_preference", "temporal_discount_rate"}:
        return 0.0, 2.0
    return 0.0, 1.0


def weighted_mean(values: list[float], weights: list[float]) -> float:
    denom = sum(weights)
    if denom <= 0:
        return sum(values) / len(values)
    return sum(v * w for v, w in zip(values, weights)) / denom


def aggregate_rows(species_rows: list[dict[str, str]], posterior_rows: list[dict[str, str]], ranks: list[str]) -> list[dict[str, object]]:
    posterior_by_species = {r["species"]: r for r in posterior_rows}
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

    species_progress = ProgressPrinter(total=len(species_rows), label="aggregate_taxon:species")
    for row in species_rows:
        species = row["species"]
        if species not in posterior_by_species:
            species_progress.tick()
            continue
        for rank in ranks:
            taxon = row.get(rank, "").strip()
            if taxon:
                groups[(rank, taxon)].append(posterior_by_species[species])
        species_progress.tick()
    species_progress.finish()

    out_rows: list[dict[str, object]] = []
    taxon_progress = ProgressPrinter(total=len(groups), label="aggregate_taxon:groups")
    for (rank, taxon), members in groups.items():
        row: dict[str, object] = {
            "entity_kind": "taxon",
            "rank": rank,
            "taxon": taxon,
            "n_species": len(members),
            "provenance_type": "imputed_taxonomy",
            "source_model": "taxon_aggregate_v1",
        }

        cal_flags = [m.get("calibration_applied", "false").strip().lower() == "true" for m in members]
        cal_refs = sorted(
            {
                ref.strip()
                for m in members
                for ref in m.get("calibration_refs", "").split("|")
                if ref.strip()
            }
        )
        row["calibration_applied"] = "true" if any(cal_flags) else "false"
        row["calibration_refs"] = "|".join(cal_refs)

        sds = [max(float(m["uncertainty_sd"]), 0.01) for m in members]
        weights = [1.0 / (sd * sd) for sd in sds]

        agg_uncertainty = math.sqrt(1.0 / sum(weights)) if sum(weights) > 0 else 0.35
        agg_uncertainty = clamp(agg_uncertainty + 0.03, 0.01, 1.0)
        row["uncertainty_sd"] = round(agg_uncertainty, 6)

        for param in PARAMS:
            vals = [float(m[param]) for m in members]
            mean_val = weighted_mean(vals, weights)
            low, high = _bounds(param)
            mean_val = clamp(mean_val, low, high)
            lower = clamp(mean_val - 1.96 * agg_uncertainty, low, high)
            upper = clamp(mean_val + 1.96 * agg_uncertainty, low, high)

            row[param] = round(mean_val, 6)
            row[f"{param}_lower"] = round(lower, 6)
            row[f"{param}_upper"] = round(upper, 6)

        out_rows.append(row)
        taxon_progress.tick()
    taxon_progress.finish()

    rank_order = {"phylum": 0, "class": 1, "order": 2, "family": 3, "genus": 4}
    out_rows.sort(key=lambda r: (rank_order.get(str(r["rank"]), 99), str(r["taxon"])))
    return out_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate species posterior priors to higher taxonomic ranks.")
    parser.add_argument("--species", required=True, help="Species seed CSV with taxonomy columns.")
    parser.add_argument("--priors", required=True, help="Species posterior priors CSV.")
    parser.add_argument("--out", required=True, help="Output CSV path for taxon priors.")
    parser.add_argument(
        "--ranks",
        default="phylum,class,order,family",
        help="Comma-separated ranks to aggregate (default: phylum,class,order,family).",
    )
    args = parser.parse_args()

    ranks = [r.strip() for r in args.ranks.split(",") if r.strip()]
    species_rows = read_csv(args.species)
    posterior_rows = read_csv(args.priors)

    out_rows = aggregate_rows(species_rows, posterior_rows, ranks=ranks)
    fields = [
        "entity_kind",
        "rank",
        "taxon",
        "n_species",
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
    print(f"Wrote taxon priors: {len(out_rows)} -> {args.out}")


if __name__ == "__main__":
    main()
