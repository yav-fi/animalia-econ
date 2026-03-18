from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.games import EntityPriors, public_goods_game, risk_choice_task, trust_game, ultimatum_game

DATASET = Path("data/processed/animaliaecon_taxon_priors.csv")


def first_entity(path: Path) -> EntityPriors:
    with open(path, "r", newline="", encoding="utf-8") as f:
        row = next(csv.DictReader(f))

    label = f"{row.get('rank', 'taxon')}={row.get('taxon', row.get('entity_name', 'unknown'))}"
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


def main() -> None:
    if not DATASET.exists():
        raise SystemExit("Dataset missing. Run make pipeline first to generate data/processed/animaliaecon_taxon_priors.csv")

    priors = first_entity(DATASET)
    print("Entity:", priors.entity)
    print("Public Goods:", public_goods_game(priors))
    print("Ultimatum:", ultimatum_game(priors))
    print("Trust:", trust_game(priors))
    print("Risk Choice:", risk_choice_task(priors))


if __name__ == "__main__":
    main()
