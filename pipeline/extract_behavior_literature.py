from __future__ import annotations

import argparse

from common import read_csv, write_csv


def build_templates(species_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in species_rows:
        rows.append(
            {
                "species": row["species"],
                "task_family": "unknown",
                "evidence_text": "No direct behavior study attached yet.",
                "evidence_confidence": 0.0,
                "source_name": "manual_curation_pending",
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Create behavior-literature extraction templates.")
    parser.add_argument("--species", required=True, help="Path to seed species CSV.")
    parser.add_argument("--out", required=True, help="Output CSV path.")
    args = parser.parse_args()

    species_rows = read_csv(args.species)
    rows = build_templates(species_rows)
    fields = ["species", "task_family", "evidence_text", "evidence_confidence", "source_name"]
    write_csv(args.out, rows, fields)
    print(f"Wrote behavior templates: {len(rows)} -> {args.out}")


if __name__ == "__main__":
    main()
