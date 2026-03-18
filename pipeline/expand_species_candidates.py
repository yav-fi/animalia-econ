from __future__ import annotations

import argparse
from collections import defaultdict

from common import ProgressPrinter, clamp, read_csv, write_csv

SEED_FIELDS = [
    "species",
    "kingdom",
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "common_name",
    "body_mass_kg",
    "sociality_score",
    "diet_breadth_score",
    "activity_pattern",
    "habitat_type",
    "source_confidence",
]

CONF_MAP = {
    "high": 0.92,
    "medium": 0.78,
    "low": 0.62,
}


def _completeness_score(row: dict[str, str], fields: list[str]) -> float:
    present = 0
    for k in fields:
        if str(row.get(k, "")).strip() != "":
            present += 1
    return present / max(1, len(fields))


def candidate_confidence_score(row: dict[str, str]) -> float:
    source_conf = CONF_MAP.get(row.get("source_confidence", "").strip().lower(), 0.55)
    taxonomy_score = _completeness_score(row, ["kingdom", "phylum", "class", "order", "family", "genus"])
    trait_score = _completeness_score(
        row,
        ["body_mass_kg", "sociality_score", "diet_breadth_score", "activity_pattern", "habitat_type"],
    )
    score = 0.55 * source_conf + 0.25 * taxonomy_score + 0.20 * trait_score
    return round(clamp(score, 0.0, 1.0), 6)


def _priority_tuple(row: dict[str, str]) -> tuple[float, str]:
    conf = CONF_MAP.get(row.get("source_confidence", "").strip().lower(), 0.55)
    return (-conf, row.get("species", ""))


def _copy_seed_row(row: dict[str, str], target_clade: str) -> dict[str, object]:
    out = {k: row.get(k, "") for k in SEED_FIELDS}
    out.update(
        {
            "is_seed": "true",
            "target_clade": target_clade,
            "candidate_source": "seed_species",
            "source_citation": "seed_species_curation",
        }
    )
    out["candidate_confidence_score"] = candidate_confidence_score(out)
    return out


def _copy_bank_row(row: dict[str, str], target_clade: str) -> dict[str, object]:
    out = {k: row.get(k, "") for k in SEED_FIELDS}
    out.update(
        {
            "is_seed": "false",
            "target_clade": target_clade,
            "candidate_source": row.get("candidate_source", "candidate_bank"),
            "source_citation": row.get("source_citation", "candidate_bank_curation"),
        }
    )
    out["candidate_confidence_score"] = candidate_confidence_score(out)
    return out


def expand_species(
    seed_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    bank_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    by_species: dict[str, dict[str, object]] = {}
    clade_counts: dict[str, int] = defaultdict(int)
    seed_counts: dict[str, int] = defaultdict(int)
    added_counts: dict[str, int] = defaultdict(int)
    missing_counts: dict[str, int] = defaultdict(int)

    target_taxa = [r for r in target_rows if r.get("rank", "").strip() == "class" and r.get("taxon", "").strip()]

    seed_progress = ProgressPrinter(total=len(seed_rows), label="expand_species:seed")
    for row in seed_rows:
        clade = row.get("class", "").strip()
        out = _copy_seed_row(row, target_clade=clade)
        by_species[str(out["species"])] = out
        if clade:
            clade_counts[clade] += 1
            seed_counts[clade] += 1
        seed_progress.tick()
    seed_progress.finish()

    bank_by_clade: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in bank_rows:
        clade = row.get("class", "").strip()
        if clade:
            bank_by_clade[clade].append(row)

    for clade, rows in bank_by_clade.items():
        rows.sort(key=_priority_tuple)

    fill_progress = ProgressPrinter(total=len(target_taxa), label="expand_species:targets")
    for target in target_taxa:
        clade = target["taxon"].strip()
        target_n = int(target.get("target_n", "0") or "0")
        current_n = clade_counts.get(clade, 0)
        need = max(target_n - current_n, 0)
        if need == 0:
            continue

        for row in bank_by_clade.get(clade, []):
            species = row.get("species", "").strip()
            if not species or species in by_species:
                continue
            by_species[species] = _copy_bank_row(row, target_clade=clade)
            clade_counts[clade] += 1
            added_counts[clade] += 1
            need -= 1
            if need == 0:
                break

        if need > 0:
            missing_counts[clade] += need
        fill_progress.tick()
    fill_progress.finish()

    expanded = sorted(by_species.values(), key=lambda r: str(r["species"]))

    coverage_rows: list[dict[str, object]] = []
    for target in target_taxa:
        clade = target["taxon"].strip()
        target_n = int(target.get("target_n", "0") or "0")
        total_n = clade_counts.get(clade, 0)
        coverage_rows.append(
            {
                "rank": "class",
                "taxon": clade,
                "target_n": target_n,
                "seed_n": seed_counts.get(clade, 0),
                "added_n": added_counts.get(clade, 0),
                "total_n": total_n,
                "coverage_ratio": round(total_n / max(1, target_n), 6),
                "shortfall_n": missing_counts.get(clade, 0),
            }
        )

    return expanded, coverage_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Expand seed species coverage by target clades and score candidate confidence."
    )
    parser.add_argument("--seed", required=True, help="Seed species CSV path.")
    parser.add_argument("--target-clades", required=True, help="Target clade CSV path.")
    parser.add_argument("--candidate-bank", required=True, help="Candidate bank CSV path.")
    parser.add_argument("--out-species", required=True, help="Expanded species CSV output path.")
    parser.add_argument("--out-coverage", required=True, help="Coverage summary CSV output path.")
    args = parser.parse_args()

    seed_rows = read_csv(args.seed)
    target_rows = read_csv(args.target_clades)
    bank_rows = read_csv(args.candidate_bank)

    expanded_rows, coverage_rows = expand_species(seed_rows, target_rows, bank_rows)

    out_fields = [
        *SEED_FIELDS,
        "is_seed",
        "target_clade",
        "candidate_source",
        "source_citation",
        "candidate_confidence_score",
    ]
    write_csv(args.out_species, expanded_rows, out_fields)
    write_csv(
        args.out_coverage,
        coverage_rows,
        ["rank", "taxon", "target_n", "seed_n", "added_n", "total_n", "coverage_ratio", "shortfall_n"],
    )

    print(f"Wrote expanded species candidates: {len(expanded_rows)} -> {args.out_species}")
    print(f"Wrote clade coverage summary: {len(coverage_rows)} -> {args.out_coverage}")


if __name__ == "__main__":
    main()
