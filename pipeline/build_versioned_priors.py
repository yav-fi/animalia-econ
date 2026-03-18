from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable

from common import ProgressPrinter, read_csv, write_csv

PARAMS = [
    "risk_preference",
    "temporal_discount_rate",
    "effort_price_elasticity",
    "cooperation_propensity",
    "inequity_sensitivity",
    "punishment_propensity",
    "tokenization_capacity",
]


def _parse_semver(value: str) -> tuple[int, int, int, str]:
    raw = (value or "").strip()
    core = raw.split("-", 1)[0]
    parts = core.split(".")
    if len(parts) >= 3 and all(p.isdigit() for p in parts[:3]):
        return int(parts[0]), int(parts[1]), int(parts[2]), raw
    return -1, -1, -1, raw


def _sorted_versions(values: Iterable[str]) -> list[str]:
    uniq = sorted({v for v in values if v}, key=lambda s: _parse_semver(s))
    return uniq


def _safe_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _p90(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(0.9 * (len(ordered) - 1))
    return ordered[idx]


def _load_release_timestamp(release_dir: Path) -> str:
    manifest = release_dir / "manifest.json"
    if not manifest.exists():
        return ""
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    return str(payload.get("released_at", "")).strip()


def _snapshot_file(version_dir: Path, filename: str) -> Path:
    return version_dir / filename


def _history_taxon_rows(source_rows: list[dict[str, str]], release_version: str, released_at: str, source_type: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in source_rows:
        out.append(
            {
                "release_version": release_version,
                "released_at": released_at,
                "source_type": source_type,
                "dataset_version": row.get("dataset_version", release_version),
                "generated_at": row.get("generated_at", ""),
                "entity_kind": row.get("entity_kind", "taxon"),
                "rank": row.get("rank", ""),
                "taxon": row.get("taxon", ""),
                "n_species": row.get("n_species", ""),
                **{p: row.get(p, "") for p in PARAMS},
                "uncertainty_sd": row.get("uncertainty_sd", ""),
                "provenance_type": row.get("provenance_type", ""),
                "source_model": row.get("source_model", ""),
            }
        )
    return out


def _history_species_rows(source_rows: list[dict[str, str]], release_version: str, released_at: str, source_type: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in source_rows:
        out.append(
            {
                "release_version": release_version,
                "released_at": released_at,
                "source_type": source_type,
                "dataset_version": row.get("dataset_version", release_version),
                "generated_at": row.get("generated_at", ""),
                "species": row.get("species", ""),
                "common_name": row.get("common_name", ""),
                "class": row.get("class", ""),
                "family": row.get("family", ""),
                **{p: row.get(p, "") for p in PARAMS},
                "uncertainty_sd": row.get("uncertainty_sd", ""),
                "row_confidence_score": row.get("row_confidence_score", ""),
                "provenance_type": row.get("provenance_type", ""),
                "source_model": row.get("source_model", ""),
            }
        )
    return out


def _build_drift_detail(
    history_rows: list[dict[str, object]],
    entity_kind: str,
) -> list[dict[str, object]]:
    key_field = "taxon" if entity_kind == "taxon" else "species"
    rank_field = "rank" if entity_kind == "taxon" else "class"

    by_entity: dict[str, list[dict[str, object]]] = {}
    for row in history_rows:
        key = str(row.get(key_field, ""))
        if not key:
            continue
        by_entity.setdefault(key, []).append(row)

    out: list[dict[str, object]] = []
    progress = ProgressPrinter(total=len(by_entity), label=f"drift_detail:{entity_kind}")
    for entity, rows in by_entity.items():
        rows_sorted = sorted(rows, key=lambda r: _parse_semver(str(r.get("release_version", ""))))
        for prev, nxt in zip(rows_sorted, rows_sorted[1:]):
            for param in PARAMS:
                a = _safe_float(str(prev.get(param, "")))
                b = _safe_float(str(nxt.get(param, "")))
                if a is None or b is None:
                    continue
                abs_delta = abs(b - a)
                pct_delta = abs_delta / abs(a) if abs(a) > 1e-9 else 0.0
                out.append(
                    {
                        "entity_kind": entity_kind,
                        "entity": entity,
                        "rank_or_class": str(prev.get(rank_field, "")),
                        "param": param,
                        "from_version": str(prev.get("release_version", "")),
                        "to_version": str(nxt.get("release_version", "")),
                        "from_value": round(a, 6),
                        "to_value": round(b, 6),
                        "abs_delta": round(abs_delta, 6),
                        "pct_delta": round(pct_delta, 6),
                    }
                )
        progress.tick()
    progress.finish()
    return out


def _build_drift_summary(detail_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str], list[float]] = {}
    changed_counts: dict[tuple[str, str, str, str], int] = {}

    for row in detail_rows:
        key = (
            str(row["entity_kind"]),
            str(row["param"]),
            str(row["from_version"]),
            str(row["to_version"]),
        )
        delta = float(row["abs_delta"])
        grouped.setdefault(key, []).append(delta)
        if delta > 1e-9:
            changed_counts[key] = changed_counts.get(key, 0) + 1

    out: list[dict[str, object]] = []
    progress = ProgressPrinter(total=len(grouped), label="drift_summary")
    for key, deltas in grouped.items():
        entity_kind, param, from_version, to_version = key
        mean_abs = sum(deltas) / max(1, len(deltas))
        out.append(
            {
                "entity_kind": entity_kind,
                "param": param,
                "from_version": from_version,
                "to_version": to_version,
                "n_entities": len(deltas),
                "n_changed": changed_counts.get(key, 0),
                "mean_abs_delta": round(mean_abs, 6),
                "p90_abs_delta": round(_p90(deltas), 6),
                "max_abs_delta": round(max(deltas), 6),
            }
        )
        progress.tick()
    progress.finish()

    out.sort(key=lambda r: (r["entity_kind"], r["param"], _parse_semver(str(r["from_version"]))))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build versioned prior histories and drift reports across releases.")
    parser.add_argument("--releases-root", default="releases/datasets", help="Release snapshots root directory.")
    parser.add_argument("--current-taxon", default="data/processed/animaliaecon_taxon_priors.csv")
    parser.add_argument("--current-species", default="data/processed/animaliaecon_species_observed.csv")
    parser.add_argument("--out-taxon-history", default="data/processed/animaliaecon_taxon_priors_history.csv")
    parser.add_argument("--out-species-history", default="data/processed/animaliaecon_species_observed_history.csv")
    parser.add_argument("--out-drift-detail", default="data/processed/animaliaecon_prior_drift_detail.csv")
    parser.add_argument("--out-drift-summary", default="data/processed/animaliaecon_prior_drift_summary.csv")
    args = parser.parse_args()

    releases_root = Path(args.releases_root)
    release_dirs = sorted([p for p in releases_root.iterdir() if p.is_dir()], key=lambda p: _parse_semver(p.name)) if releases_root.exists() else []

    taxon_history: list[dict[str, object]] = []
    species_history: list[dict[str, object]] = []

    release_progress = ProgressPrinter(total=len(release_dirs), label="versioned_priors:releases")
    for rel in release_dirs:
        taxon_file = _snapshot_file(rel, "animaliaecon_taxon_priors.csv")
        species_file = _snapshot_file(rel, "animaliaecon_species_observed.csv")
        released_at = _load_release_timestamp(rel)
        if taxon_file.exists():
            taxon_history.extend(_history_taxon_rows(read_csv(taxon_file), rel.name, released_at, "snapshot"))
        if species_file.exists():
            species_history.extend(_history_species_rows(read_csv(species_file), rel.name, released_at, "snapshot"))
        release_progress.tick()
    release_progress.finish()

    current_taxon_rows = read_csv(args.current_taxon)
    current_species_rows = read_csv(args.current_species)
    current_ver_taxon = current_taxon_rows[0].get("dataset_version", "current") if current_taxon_rows else "current"
    current_ver_species = current_species_rows[0].get("dataset_version", "current") if current_species_rows else "current"

    taxon_history.extend(_history_taxon_rows(current_taxon_rows, current_ver_taxon, "", "working_tree"))
    species_history.extend(_history_species_rows(current_species_rows, current_ver_species, "", "working_tree"))

    taxon_history.sort(key=lambda r: (_parse_semver(str(r["release_version"])), str(r["rank"]), str(r["taxon"])))
    species_history.sort(key=lambda r: (_parse_semver(str(r["release_version"])), str(r["species"])))

    write_csv(
        args.out_taxon_history,
        taxon_history,
        [
            "release_version",
            "released_at",
            "source_type",
            "dataset_version",
            "generated_at",
            "entity_kind",
            "rank",
            "taxon",
            "n_species",
            *PARAMS,
            "uncertainty_sd",
            "provenance_type",
            "source_model",
        ],
    )
    write_csv(
        args.out_species_history,
        species_history,
        [
            "release_version",
            "released_at",
            "source_type",
            "dataset_version",
            "generated_at",
            "species",
            "common_name",
            "class",
            "family",
            *PARAMS,
            "uncertainty_sd",
            "row_confidence_score",
            "provenance_type",
            "source_model",
        ],
    )

    drift_detail = _build_drift_detail(taxon_history, entity_kind="taxon") + _build_drift_detail(
        species_history,
        entity_kind="species",
    )
    drift_summary = _build_drift_summary(drift_detail)
    write_csv(
        args.out_drift_detail,
        drift_detail,
        [
            "entity_kind",
            "entity",
            "rank_or_class",
            "param",
            "from_version",
            "to_version",
            "from_value",
            "to_value",
            "abs_delta",
            "pct_delta",
        ],
    )
    write_csv(
        args.out_drift_summary,
        drift_summary,
        [
            "entity_kind",
            "param",
            "from_version",
            "to_version",
            "n_entities",
            "n_changed",
            "mean_abs_delta",
            "p90_abs_delta",
            "max_abs_delta",
        ],
    )

    versions = _sorted_versions([str(r.get("release_version", "")) for r in taxon_history + species_history])
    print(f"Wrote taxon prior history: {len(taxon_history)} -> {args.out_taxon_history}")
    print(f"Wrote species prior history: {len(species_history)} -> {args.out_species_history}")
    print(f"Wrote drift detail: {len(drift_detail)} -> {args.out_drift_detail}")
    print(f"Wrote drift summary: {len(drift_summary)} -> {args.out_drift_summary}")
    print(f"Versions tracked: {', '.join(versions) if versions else 'none'}")


if __name__ == "__main__":
    main()
