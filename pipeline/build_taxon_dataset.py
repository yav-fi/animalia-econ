from __future__ import annotations

import argparse
import datetime as dt
import os

from common import ProgressPrinter, read_csv, write_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Build release-ready taxon-first AnimaliaEcon dataset.")
    parser.add_argument("--taxon-priors", required=True, help="Aggregated taxon priors CSV.")
    parser.add_argument("--out", required=True, help="Output processed CSV path.")
    parser.add_argument(
        "--dataset-version",
        default=os.getenv("ANIMALIA_ECON_DATASET_VERSION", "0.4.0"),
        help="Dataset semantic version.",
    )
    args = parser.parse_args()

    rows = read_csv(args.taxon_priors)
    generated_at = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    out_rows: list[dict[str, object]] = []
    progress = ProgressPrinter(total=len(rows), label="build_taxon_dataset")
    for row in rows:
        merged = {
            "dataset_version": args.dataset_version,
            "generated_at": generated_at,
            "entity_kind": "taxon",
            "entity_name": row["taxon"],
            **row,
        }
        out_rows.append(merged)
        progress.tick()
    progress.finish()

    if not out_rows:
        raise SystemExit("No taxon rows to write. Check input.")

    write_csv(args.out, out_rows, list(out_rows[0].keys()))
    print(f"Wrote taxon release dataset: {len(out_rows)} -> {args.out}")


if __name__ == "__main__":
    main()
