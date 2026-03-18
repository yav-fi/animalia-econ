from __future__ import annotations

import argparse
import datetime as dt
import os

from common import ProgressPrinter, read_csv, write_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Build species-observed AnimaliaEcon priors dataset.")
    parser.add_argument("--species", required=True, help="Species seed CSV.")
    parser.add_argument("--priors", required=True, help="Posterior priors CSV.")
    parser.add_argument("--out", required=True, help="Output processed CSV path.")
    parser.add_argument(
        "--dataset-version",
        default=os.getenv("ANIMALIA_ECON_DATASET_VERSION", "0.4.0"),
        help="Dataset semantic version.",
    )
    args = parser.parse_args()

    species_rows = {r["species"]: r for r in read_csv(args.species)}
    prior_rows = read_csv(args.priors)

    generated_at = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    out_rows: list[dict[str, object]] = []
    progress = ProgressPrinter(total=len(prior_rows), label="build_dataset")

    for pr in prior_rows:
        sp = species_rows.get(pr["species"])
        if not sp:
            progress.tick()
            continue

        merged = {
            "dataset_version": args.dataset_version,
            "generated_at": generated_at,
            "species": pr["species"],
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
        }
        merged.update(pr)
        out_rows.append(merged)
        progress.tick()
    progress.finish()

    if not out_rows:
        raise SystemExit("No merged rows generated. Check input files.")

    fields = list(out_rows[0].keys())
    write_csv(args.out, out_rows, fields)
    print(f"Wrote release dataset: {len(out_rows)} -> {args.out}")


if __name__ == "__main__":
    main()
