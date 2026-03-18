from __future__ import annotations

import argparse

from common import ProgressPrinter, read_csv, write_csv


def _safe_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def main() -> None:
    parser = argparse.ArgumentParser(description="Build manual curation queue for low-confidence species rows.")
    parser.add_argument("--species-observed", required=True, help="Processed species-observed dataset CSV.")
    parser.add_argument("--out", required=True, help="Review queue CSV output path.")
    parser.add_argument("--min-confidence", type=float, default=0.72, help="Row confidence threshold.")
    parser.add_argument("--max-uncertainty", type=float, default=0.28, help="Uncertainty threshold.")
    args = parser.parse_args()

    rows = read_csv(args.species_observed)
    queue: list[dict[str, object]] = []
    progress = ProgressPrinter(total=len(rows), label="override_queue")

    for row in rows:
        confidence = _safe_float(row.get("row_confidence_score", ""), 0.0)
        uncertainty = _safe_float(row.get("uncertainty_sd", ""), 1.0)
        provenance = row.get("provenance_type", "").strip()

        reasons: list[str] = []
        if confidence < args.min_confidence:
            reasons.append("low_row_confidence")
        if uncertainty > args.max_uncertainty:
            reasons.append("high_uncertainty")

        if not reasons:
            progress.tick()
            continue
        if provenance in {"imputed_trait", "inherited_taxonomy"}:
            reasons.append("imputed_row")

        severity = (args.min_confidence - confidence) + (uncertainty - args.max_uncertainty)
        queue.append(
            {
                "species": row.get("species", ""),
                "common_name": row.get("common_name", ""),
                "class": row.get("class", ""),
                "family": row.get("family", ""),
                "row_confidence_score": round(confidence, 6),
                "uncertainty_sd": round(uncertainty, 6),
                "provenance_type": provenance,
                "review_reasons": "|".join(sorted(set(reasons))),
                "severity_score": round(severity, 6),
                "recommended_override_file": "data/curation/species_overrides.csv",
            }
        )
        progress.tick()
    progress.finish()

    queue.sort(key=lambda r: float(r["severity_score"]), reverse=True)
    write_csv(
        args.out,
        queue,
        [
            "species",
            "common_name",
            "class",
            "family",
            "row_confidence_score",
            "uncertainty_sd",
            "provenance_type",
            "review_reasons",
            "severity_score",
            "recommended_override_file",
        ],
    )
    print(f"Wrote override review queue: {len(queue)} -> {args.out}")


if __name__ == "__main__":
    main()
