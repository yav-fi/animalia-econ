from __future__ import annotations

import argparse
import csv
from pathlib import Path

from sim.games import EntityPriors, public_goods_game, risk_choice_task, trust_game, ultimatum_game

DEFAULT_TAXON_DATASET = Path("data/processed/animaliaecon_taxon_priors.csv")


def _to_priors(row: dict[str, str], label: str) -> EntityPriors:
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


def load_entity_priors(dataset_path: Path, entity: str, entity_kind: str, rank: str | None = None) -> EntityPriors:
    with open(dataset_path, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    want = entity.strip().lower()

    if entity_kind == "taxon":
        candidates = [r for r in rows if r.get("taxon", "").strip().lower() == want or r.get("entity_name", "").strip().lower() == want]
        if rank:
            candidates = [r for r in candidates if r.get("rank", "").strip().lower() == rank.strip().lower()]
        if not candidates:
            raise SystemExit(f"Taxon not found in dataset: {entity}")
        row = candidates[0]
        label = f"{row.get('rank', 'taxon')}={row.get('taxon', row.get('entity_name', entity))}"
        return _to_priors(row, label=label)

    for row in rows:
        if row.get("species", "").strip().lower() == want:
            return _to_priors(row, label=row["species"])

    raise SystemExit(f"Species not found in dataset: {entity}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AnimaliaEcon game simulations for taxa or species.")
    parser.add_argument("game", choices=["public-goods", "ultimatum", "trust", "risk-choice"])
    parser.add_argument("--entity", required=True, help="Taxon name (default) or species name.")
    parser.add_argument("--entity-kind", choices=["taxon", "species"], default="taxon", help="Entity type to load.")
    parser.add_argument("--rank", default=None, help="Taxonomic rank for taxon lookup (for example class or family).")
    parser.add_argument("--dataset", default=str(DEFAULT_TAXON_DATASET), help="Path to processed priors CSV.")
    args = parser.parse_args()

    priors = load_entity_priors(Path(args.dataset), args.entity, args.entity_kind, rank=args.rank)

    if args.game == "public-goods":
        result = public_goods_game(priors)
    elif args.game == "ultimatum":
        result = ultimatum_game(priors)
    elif args.game == "trust":
        result = trust_game(priors)
    else:
        result = risk_choice_task(priors)

    print(f"Entity: {priors.entity}")
    print(f"Game: {args.game}")
    for k, v in result.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
