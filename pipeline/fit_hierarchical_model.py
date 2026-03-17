from __future__ import annotations

import argparse
import math
from collections import defaultdict

from common import clamp, read_csv, write_csv

PARAMS = [
    "risk_preference",
    "temporal_discount_rate",
    "effort_price_elasticity",
    "cooperation_propensity",
    "inequity_sensitivity",
    "punishment_propensity",
    "tokenization_capacity",
]


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply taxonomic shrinkage to prior estimates.")
    parser.add_argument("--species", required=True, help="Seed species CSV with taxonomy columns.")
    parser.add_argument("--priors", required=True, help="Estimated priors CSV.")
    parser.add_argument("--out", required=True, help="Output posterior CSV.")
    args = parser.parse_args()

    species_rows = read_csv(args.species)
    prior_rows = {r["species"]: r for r in read_csv(args.priors)}

    class_buckets: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    family_buckets: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    global_buckets: dict[str, list[float]] = defaultdict(list)

    for row in species_rows:
        pr = prior_rows.get(row["species"])
        if not pr:
            continue
        cls = row["class"]
        fam = row["family"]
        for p in PARAMS:
            value = float(pr[p])
            class_buckets[cls][p].append(value)
            family_buckets[fam][p].append(value)
            global_buckets[p].append(value)

    out_rows: list[dict[str, object]] = []

    for row in species_rows:
        pr = prior_rows.get(row["species"])
        if not pr:
            continue

        cls = row["class"]
        fam = row["family"]
        fam_size = len(family_buckets[fam][PARAMS[0]])

        result: dict[str, object] = {
            "species": row["species"],
            "class": cls,
            "family": fam,
            "provenance_type": pr["provenance_type"],
            "source_model": pr["source_model"],
        }

        base_sd = float(pr["uncertainty_sd"])
        shrink_factor = clamp(1.0 / math.sqrt(max(1, fam_size)), 0.45, 1.0)
        posterior_sd = round(clamp(base_sd * shrink_factor, 0.01, 1.0), 6)
        result["uncertainty_sd"] = posterior_sd

        for p in PARAMS:
            observed = float(pr[p])
            global_mean = mean(global_buckets[p])
            class_mean = mean(class_buckets[cls][p])
            family_mean = mean(family_buckets[fam][p])
            posterior = 0.20 * global_mean + 0.35 * class_mean + 0.35 * family_mean + 0.10 * observed

            if p == "effort_price_elasticity":
                posterior = clamp(posterior, -3.0, 1.0)
            elif p in {"risk_preference", "temporal_discount_rate"}:
                posterior = clamp(posterior, 0.0, 2.0)
            else:
                posterior = clamp(posterior, 0.0, 1.0)

            lower = posterior - 1.96 * posterior_sd
            upper = posterior + 1.96 * posterior_sd

            if p == "effort_price_elasticity":
                lower, upper = clamp(lower, -3.0, 1.0), clamp(upper, -3.0, 1.0)
            elif p in {"risk_preference", "temporal_discount_rate"}:
                lower, upper = clamp(lower, 0.0, 2.0), clamp(upper, 0.0, 2.0)
            else:
                lower, upper = clamp(lower, 0.0, 1.0), clamp(upper, 0.0, 1.0)

            result[p] = round(posterior, 6)
            result[f"{p}_lower"] = round(lower, 6)
            result[f"{p}_upper"] = round(upper, 6)

        out_rows.append(result)

    fields = [
        "species",
        "class",
        "family",
        *PARAMS,
        *[f"{p}_lower" for p in PARAMS],
        *[f"{p}_upper" for p in PARAMS],
        "uncertainty_sd",
        "provenance_type",
        "source_model",
    ]
    write_csv(args.out, out_rows, fields)
    print(f"Wrote posterior priors: {len(out_rows)} -> {args.out}")


if __name__ == "__main__":
    main()
