from __future__ import annotations

import argparse
import math

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


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _weight(n_studies: int, target_sd: float, alpha: float, max_weight: float) -> float:
    n_term = n_studies / (n_studies + max(alpha, 1e-6))
    sd_term = 1.0 / (1.0 + max(target_sd, 0.01) * 8.0)
    return clamp(n_term * sd_term, 0.05, max_weight)


def _param_sd_from_row(row: dict[str, str], param: str) -> float:
    low_key = f"{param}_lower"
    high_key = f"{param}_upper"
    if low_key in row and high_key in row:
        lo = float(row[low_key])
        hi = float(row[high_key])
        if hi > lo:
            return max((hi - lo) / (2.0 * 1.96), 0.01)
    return max(float(row["uncertainty_sd"]), 0.01)


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate species posteriors to clade-level behavioral study anchors.")
    parser.add_argument("--species", required=True, help="Species CSV with taxonomy columns.")
    parser.add_argument("--priors", required=True, help="Species posterior priors CSV.")
    parser.add_argument("--calibration", required=True, help="Calibration anchors CSV.")
    parser.add_argument("--out", required=True, help="Output calibrated posterior CSV.")
    parser.add_argument("--audit-out", required=True, help="Calibration audit CSV output.")
    parser.add_argument("--alpha", type=float, default=8.0, help="Pseudo-count controlling calibration strength.")
    parser.add_argument("--max-weight", type=float, default=0.85, help="Upper bound on calibration weight.")
    args = parser.parse_args()

    species_rows = read_csv(args.species)
    priors_rows = read_csv(args.priors)
    calibration_rows = read_csv(args.calibration)

    species_by_name = {r["species"]: r for r in species_rows}
    priors_by_species = {r["species"]: dict(r) for r in priors_rows}

    for row in priors_by_species.values():
        row["calibration_applied"] = "false"
        row["calibration_refs"] = row.get("calibration_refs", "")

    audit_rows: list[dict[str, object]] = []

    progress = ProgressPrinter(total=len(calibration_rows), label="calibrate_priors")
    for cal in calibration_rows:
        rank = cal.get("rank", "").strip()
        taxon = cal.get("taxon", "").strip()
        param = cal.get("param", "").strip()
        if rank not in {"phylum", "class", "order", "family", "genus"}:
            progress.tick()
            continue
        if param not in PARAMS:
            progress.tick()
            continue

        target_mean = float(cal["target_mean"])
        target_sd = max(float(cal["target_sd"]), 0.01)
        n_studies = max(int(cal.get("n_studies", "1") or "1"), 1)
        citation = cal.get("citation", "").strip()
        note = cal.get("note", "").strip()

        matched_species = [
            sp
            for sp, srow in species_by_name.items()
            if srow.get(rank, "").strip() == taxon and sp in priors_by_species
        ]

        if not matched_species:
            audit_rows.append(
                {
                    "rank": rank,
                    "taxon": taxon,
                    "param": param,
                    "matched_n": 0,
                    "target_mean": target_mean,
                    "current_mean": "",
                    "weight": 0.0,
                    "adjustment": 0.0,
                    "citation": citation,
                    "note": note,
                    "status": "no_match",
                }
            )
            progress.tick()
            continue

        current_vals = [float(priors_by_species[sp][param]) for sp in matched_species]
        current_mean = _mean(current_vals)
        weight = _weight(n_studies=n_studies, target_sd=target_sd, alpha=args.alpha, max_weight=args.max_weight)
        adjustment = weight * (target_mean - current_mean)
        low, high = _bounds(param)

        for sp in matched_species:
            row = priors_by_species[sp]
            old_val = float(row[param])
            new_val = clamp(old_val + adjustment, low, high)

            old_sd = max(float(row["uncertainty_sd"]), 0.01)
            added_sd = weight * target_sd
            new_uncertainty = clamp(math.sqrt(old_sd * old_sd + added_sd * added_sd), 0.01, 1.0)

            param_sd = _param_sd_from_row(row, param)
            new_param_sd = math.sqrt(param_sd * param_sd + added_sd * added_sd)

            row[param] = f"{new_val:.6f}"
            row[f"{param}_lower"] = f"{clamp(new_val - 1.96 * new_param_sd, low, high):.6f}"
            row[f"{param}_upper"] = f"{clamp(new_val + 1.96 * new_param_sd, low, high):.6f}"
            row["uncertainty_sd"] = f"{new_uncertainty:.6f}"
            row["calibration_applied"] = "true"

            refs = {x for x in row.get("calibration_refs", "").split("|") if x}
            if citation:
                refs.add(citation)
            row["calibration_refs"] = "|".join(sorted(refs))

        audit_rows.append(
            {
                "rank": rank,
                "taxon": taxon,
                "param": param,
                "matched_n": len(matched_species),
                "target_mean": round(target_mean, 6),
                "current_mean": round(current_mean, 6),
                "weight": round(weight, 6),
                "adjustment": round(adjustment, 6),
                "citation": citation,
                "note": note,
                "status": "applied",
            }
        )
        progress.tick()
    progress.finish()

    out_fields = list(priors_rows[0].keys()) + ["calibration_applied", "calibration_refs"]
    out_rows = [priors_by_species[r["species"]] for r in priors_rows if r["species"] in priors_by_species]

    write_csv(args.out, out_rows, out_fields)
    write_csv(
        args.audit_out,
        audit_rows,
        [
            "rank",
            "taxon",
            "param",
            "matched_n",
            "target_mean",
            "current_mean",
            "weight",
            "adjustment",
            "citation",
            "note",
            "status",
        ],
    )

    applied_n = sum(1 for r in audit_rows if r["status"] == "applied")
    print(f"Wrote calibrated priors: {len(out_rows)} -> {args.out}")
    print(f"Wrote calibration audit: {len(audit_rows)} rows ({applied_n} applied) -> {args.audit_out}")


if __name__ == "__main__":
    main()
