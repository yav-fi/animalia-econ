from __future__ import annotations

import argparse
import math

from common import ProgressPrinter, clamp, read_csv, write_csv

_ACTIVITY_MAP = {
    "diurnal": 1.0,
    "crepuscular": 0.5,
    "nocturnal": 0.0,
}

_HABITAT_MAP = {
    "urban": 0.2,
    "terrestrial": 0.6,
    "forest": 0.8,
    "freshwater": 0.5,
    "marine": 0.4,
    "mixed": 0.7,
    "montane": 0.65,
}


def normalize(seed_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    progress = ProgressPrinter(total=len(seed_rows), label="extract_traits")
    for row in seed_rows:
        mass = float(row["body_mass_kg"])
        sociality = float(row["sociality_score"])
        diet = float(row["diet_breadth_score"])
        activity = _ACTIVITY_MAP.get(row["activity_pattern"].strip().lower(), 0.5)
        habitat = _HABITAT_MAP.get(row["habitat_type"].strip().lower(), 0.5)

        log_mass = math.log10(max(mass, 1e-9))
        # Approximate scaling in [0, 1] from log10 mass in [-9, 2]
        mass_scaled = clamp((log_mass + 9.0) / 11.0, 0.0, 1.0)

        rows.append(
            {
                "species": row["species"],
                "mass_scaled": round(mass_scaled, 6),
                "sociality_score": sociality,
                "diet_breadth_score": diet,
                "activity_score": activity,
                "habitat_complexity_score": habitat,
                "source_confidence": row["source_confidence"],
            }
        )
        progress.tick()
    progress.finish()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize seed traits for prior modeling.")
    parser.add_argument("--seed", required=True, help="Path to seed species CSV.")
    parser.add_argument("--out", required=True, help="Output CSV path.")
    args = parser.parse_args()

    seed_rows = read_csv(args.seed)
    rows = normalize(seed_rows)
    fields = [
        "species",
        "mass_scaled",
        "sociality_score",
        "diet_breadth_score",
        "activity_score",
        "habitat_complexity_score",
        "source_confidence",
    ]
    write_csv(args.out, rows, fields)
    print(f"Wrote normalized traits: {len(rows)} -> {args.out}")


if __name__ == "__main__":
    main()
