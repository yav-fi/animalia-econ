from __future__ import annotations

import base64
import csv
import os
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

from sim.games import EntityPriors, public_goods_game, risk_choice_task, trust_game, ultimatum_game

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TAXON_DATASET = ROOT / "data/processed/animaliaecon_taxon_priors.csv"
DEFAULT_SPECIES_INHERITED = ROOT / "data/processed/animaliaecon_species_inherited.csv"
DEFAULT_SPECIES_OBSERVED = ROOT / "data/processed/animaliaecon_species_observed.csv"
DEFAULT_RELEASES_ROOT = ROOT / "releases/datasets"

SNAPSHOT_TAXON = "animaliaecon_taxon_priors.csv"
SNAPSHOT_SPECIES_INHERITED = "animaliaecon_species_inherited.csv"
SNAPSHOT_SPECIES_OBSERVED = "animaliaecon_species_observed.csv"

FISH_CLASSES = {"actinopterygii", "chondrichthyes", "sarcopterygii"}


@lru_cache(maxsize=64)
def _load_csv_cached(path_str: str, mtime_ns: int, size: int) -> list[dict[str, str]]:
    del mtime_ns, size
    with open(path_str, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    stat = path.stat()
    return _load_csv_cached(str(path), stat.st_mtime_ns, stat.st_size)


def resolve_datasets() -> dict[str, Path]:
    return {
        "taxon": Path(os.getenv("ANIMALIA_ECON_TAXON_DATASET", str(DEFAULT_TAXON_DATASET))),
        "species_inherited": Path(os.getenv("ANIMALIA_ECON_SPECIES_INHERITED", str(DEFAULT_SPECIES_INHERITED))),
        "species_observed": Path(os.getenv("ANIMALIA_ECON_SPECIES_OBSERVED", str(DEFAULT_SPECIES_OBSERVED))),
    }


def _releases_root() -> Path:
    return Path(os.getenv("ANIMALIA_ECON_RELEASES_ROOT", str(DEFAULT_RELEASES_ROOT)))


def _parse_semver(value: str) -> tuple[int, int, int, str]:
    raw = (value or "").strip()
    core = raw.split("-", 1)[0]
    parts = core.split(".")
    if len(parts) >= 3 and all(p.isdigit() for p in parts[:3]):
        return int(parts[0]), int(parts[1]), int(parts[2]), raw
    return -1, -1, -1, raw


def list_snapshot_versions() -> list[str]:
    root = _releases_root()
    if not root.exists():
        return []
    versions = [p.name for p in root.iterdir() if p.is_dir()]
    return sorted(versions, key=_parse_semver, reverse=True)


def _current_dataset_version() -> str:
    rows = load_csv(resolve_datasets()["taxon"])
    if rows:
        version = rows[0].get("dataset_version", "").strip()
        if version:
            return version
    return "current"


def resolve_versioned_paths(dataset_version: str | None = None) -> tuple[dict[str, Path], str]:
    requested = (dataset_version or "").strip()
    current_version = _current_dataset_version()
    if not requested or requested in {"latest", "current"} or requested == current_version:
        return resolve_datasets(), current_version

    snapshot_root = _releases_root() / requested
    if not snapshot_root.exists():
        raise ValueError(f"Unknown dataset_version: {requested}")

    paths = {
        "taxon": snapshot_root / SNAPSHOT_TAXON,
        "species_inherited": snapshot_root / SNAPSHOT_SPECIES_INHERITED,
        "species_observed": snapshot_root / SNAPSHOT_SPECIES_OBSERVED,
    }
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        raise ValueError(f"Incomplete snapshot for dataset_version={requested}: missing {', '.join(missing)}")
    return paths, requested


def list_taxa(
    rank: str | None = None,
    taxon_query: str | None = None,
    limit: int = 100,
    offset: int = 0,
    dataset_version: str | None = None,
) -> list[dict[str, str]]:
    paths, _ = resolve_versioned_paths(dataset_version=dataset_version)
    rows = load_csv(paths["taxon"])

    out = rows
    if rank:
        rank_l = rank.strip().lower()
        out = [r for r in out if r.get("rank", "").strip().lower() == rank_l]
    if taxon_query:
        q = taxon_query.strip().lower()
        out = [r for r in out if q in r.get("taxon", "").strip().lower()]

    return out[offset : offset + max(1, min(limit, 500))]


def get_taxon(rank: str, taxon: str, dataset_version: str | None = None) -> dict[str, str] | None:
    rank_l = rank.strip().lower()
    taxon_l = taxon.strip().lower()
    paths, _ = resolve_versioned_paths(dataset_version=dataset_version)
    rows = load_csv(paths["taxon"])
    for row in rows:
        if row.get("rank", "").strip().lower() == rank_l and row.get("taxon", "").strip().lower() == taxon_l:
            return row
    return None


def get_species(species: str, dataset: str = "inherited", dataset_version: str | None = None) -> dict[str, str] | None:
    key = "species_inherited" if dataset == "inherited" else "species_observed"
    paths, _ = resolve_versioned_paths(dataset_version=dataset_version)
    rows = load_csv(paths[key])
    target = species.strip().lower()
    for row in rows:
        if row.get("species", "").strip().lower() == target:
            return row
    return None


def build_species_id(species: str, dataset: str = "inherited", dataset_version: str | None = None) -> str:
    version = (dataset_version or "latest").strip() or "latest"
    payload = f"{version}|{dataset}|{species.strip()}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def parse_species_id(species_id: str) -> tuple[str | None, str, str]:
    if not species_id:
        raise ValueError("species_id is required")
    padded = species_id + ("=" * ((4 - len(species_id) % 4) % 4))
    try:
        payload = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Invalid species_id") from exc
    parts = payload.split("|")
    if len(parts) == 2:
        # Backward compatibility: dataset|species
        dataset, species = parts[0].strip(), parts[1].strip()
        if dataset not in {"inherited", "observed"} or not species:
            raise ValueError("Invalid species_id")
        return None, dataset, species
    if len(parts) == 3:
        version, dataset, species = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if dataset not in {"inherited", "observed"} or not species:
            raise ValueError("Invalid species_id")
        return (version if version and version != "latest" else None), dataset, species
    raise ValueError("Invalid species_id")


def _row_bucket(row: dict[str, str]) -> str | None:
    class_l = row.get("class", "").strip().lower()
    if class_l == "mammalia":
        return "mammal"
    if class_l == "aves":
        return "bird"
    if class_l == "insecta":
        return "insect"
    if class_l in FISH_CLASSES:
        return "fish"
    return None


def _search_score(row: dict[str, str], q: str) -> tuple[int, int, int]:
    sci = row.get("species", "").strip().lower()
    common = row.get("common_name", "").strip().lower()
    q = q.strip().lower()

    if not q:
        return (9, 9_999, 9_999)
    if q == sci or q == common:
        return (0, 0, len(sci))

    starts = min((idx for idx, s in enumerate((common, sci)) if s.startswith(q)), default=9_999)
    if starts != 9_999:
        return (1, starts, len(sci))

    contains = min((s.find(q) for s in (common, sci) if q in s), default=9_999)
    if contains != 9_999:
        return (2, contains, len(sci))

    return (9, 9_999, 9_999)


def species_label(row: dict[str, str]) -> str:
    species = row.get("species", "").strip()
    common = row.get("common_name", "").strip()
    if common and species:
        return f"{common} ({species})"
    return species or common


def _species_rows(dataset: str = "inherited", dataset_version: str | None = None) -> tuple[list[dict[str, str]], str]:
    key = "species_inherited" if dataset == "inherited" else "species_observed"
    paths, resolved_version = resolve_versioned_paths(dataset_version=dataset_version)
    return load_csv(paths[key]), resolved_version


def search_species(
    query: str,
    dataset: str = "inherited",
    limit: int = 5,
    dataset_version: str | None = None,
) -> list[dict[str, str]]:
    q = query.strip().lower()
    rows, resolved_version = _species_rows(dataset=dataset, dataset_version=dataset_version)
    scored = []
    for row in rows:
        score = _search_score(row, q)
        if score[0] >= 9:
            continue
        scored.append((score, row))

    scored.sort(key=lambda item: (item[0], item[1].get("species", "")))
    out: list[dict[str, str]] = []
    for _, row in scored[: max(1, min(limit, 25))]:
        species = row.get("species", "").strip()
        out.append(
            {
                "id": build_species_id(species, dataset=dataset, dataset_version=resolved_version),
                "dataset": dataset,
                "dataset_version": resolved_version,
                "label": species_label(row),
                "species": species,
                "common_name": row.get("common_name", ""),
                "bucket": _row_bucket(row) or "",
            }
        )
    return out


def get_species_by_id(species_id: str, dataset_version_override: str | None = None) -> dict[str, Any] | None:
    id_version, dataset, species = parse_species_id(species_id)
    version = dataset_version_override or id_version
    row = get_species(species, dataset=dataset, dataset_version=version)
    if row is None:
        return None
    _, resolved_version = resolve_versioned_paths(dataset_version=version)
    return {
        "id": species_id,
        "dataset": dataset,
        "dataset_version": resolved_version,
        "label": species_label(row),
        "row": row,
    }


def random_species(dataset: str = "inherited", bucket: str | None = None, dataset_version: str | None = None) -> dict[str, Any]:
    rows, resolved_version = _species_rows(dataset=dataset, dataset_version=dataset_version)
    if not rows:
        raise ValueError("Species dataset is empty")

    requested_bucket = (bucket or "").strip().lower()
    matched_bucket = False
    pool = rows
    if requested_bucket in {"mammal", "bird", "insect", "fish"}:
        filtered = [r for r in rows if _row_bucket(r) == requested_bucket]
        if filtered:
            pool = filtered
            matched_bucket = True

    row = random.choice(pool)
    species = row.get("species", "").strip()
    return {
        "id": build_species_id(species, dataset=dataset, dataset_version=resolved_version),
        "dataset": dataset,
        "dataset_version": resolved_version,
        "label": species_label(row),
        "requested_bucket": requested_bucket or None,
        "matched_bucket": matched_bucket,
        "row": row,
    }


def row_to_priors(row: dict[str, str], label: str) -> EntityPriors:
    return EntityPriors(
        entity=label,
        risk_preference=float(row["risk_preference"]),
        temporal_discount_rate=float(row["temporal_discount_rate"]),
        effort_price_elasticity=float(row["effort_price_elasticity"]),
        cooperation_propensity=float(row["cooperation_propensity"]),
        inequity_sensitivity=float(row["inequity_sensitivity"]),
        punishment_propensity=float(row["punishment_propensity"]),
        tokenization_capacity=float(row["tokenization_capacity"]),
    )


def simulate(game: str, priors: EntityPriors, rounds: int | None = None, trials: int | None = None) -> dict[str, Any]:
    if game == "public-goods":
        return public_goods_game(priors, rounds=rounds or 10)
    if game == "ultimatum":
        return ultimatum_game(priors, rounds=rounds or 20)
    if game == "trust":
        return trust_game(priors, rounds=rounds or 20)
    if game == "risk-choice":
        return risk_choice_task(priors, trials=trials or 100)
    raise ValueError(f"Unsupported game: {game}")


def dataset_stats(dataset_version: str | None = None) -> dict[str, Any]:
    paths, resolved_version = resolve_versioned_paths(dataset_version=dataset_version)
    versions = list_snapshot_versions()
    if resolved_version not in versions:
        versions = sorted([resolved_version, *versions], key=_parse_semver, reverse=True)
    return {
        "dataset_version": resolved_version,
        "available_versions": versions,
        "taxon_rows": len(load_csv(paths["taxon"])),
        "species_inherited_rows": len(load_csv(paths["species_inherited"])),
        "species_observed_rows": len(load_csv(paths["species_observed"])),
    }
