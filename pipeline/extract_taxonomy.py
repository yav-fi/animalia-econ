from __future__ import annotations

import argparse

from common import read_csv, stable_id, utc_now_iso, write_csv


def build_taxonomy_rows(seed_rows: list[dict[str, str]], source: str, source_version: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    retrieved_at = utc_now_iso()
    for row in seed_rows:
        species = row["species"].strip()
        out.append(
            {
                "species_id": stable_id(species, prefix="sp"),
                "species": species,
                "kingdom": row["kingdom"],
                "phylum": row["phylum"],
                "class": row["class"],
                "order": row["order"],
                "family": row["family"],
                "genus": row["genus"],
                "common_name": row["common_name"],
                "taxonomy_source": source,
                "source_version": source_version,
                "retrieved_at": retrieved_at,
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build taxonomy backbone from seed species.")
    parser.add_argument("--seed", required=True, help="Path to seed species CSV.")
    parser.add_argument("--out", required=True, help="Output CSV path.")
    parser.add_argument("--source", default="catalogue_of_life", help="Taxonomy source name.")
    parser.add_argument("--source-version", default="2026-02", help="Taxonomy source version.")
    args = parser.parse_args()

    seed_rows = read_csv(args.seed)
    rows = build_taxonomy_rows(seed_rows, source=args.source, source_version=args.source_version)
    fields = [
        "species_id",
        "species",
        "kingdom",
        "phylum",
        "class",
        "order",
        "family",
        "genus",
        "common_name",
        "taxonomy_source",
        "source_version",
        "retrieved_at",
    ]
    write_csv(args.out, rows, fields)
    print(f"Wrote taxonomy rows: {len(rows)} -> {args.out}")


if __name__ == "__main__":
    main()
