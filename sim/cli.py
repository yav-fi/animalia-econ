from __future__ import annotations

import argparse
import csv
from pathlib import Path

from sim.games import SpeciesPriors, public_goods_game, risk_choice_task, trust_game, ultimatum_game

DEFAULT_DATASET = Path("data/processed/animaliaecon_priors.csv")


def load_species_priors(dataset_path: Path, species: str) -> SpeciesPriors:
    with open(dataset_path, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        if row["species"].strip().lower() == species.strip().lower():
            return SpeciesPriors(
                species=row["species"],
                risk_preference=float(row["risk_preference"]),
                temporal_discount_rate=float(row["temporal_discount_rate"]),
                effort_price_elasticity=float(row["effort_price_elasticity"]),
                cooperation_propensity=float(row["cooperation_propensity"]),
                inequity_sensitivity=float(row["inequity_sensitivity"]),
                punishment_propensity=float(row["punishment_propensity"]),
                tokenization_capacity=float(row["tokenization_capacity"]),
            )

    raise SystemExit(f"Species not found in dataset: {species}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AnimaliaEcon game simulations for a species.")
    parser.add_argument("game", choices=["public-goods", "ultimatum", "trust", "risk-choice"])
    parser.add_argument("--species", required=True, help="Species scientific name.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Path to processed priors CSV.")
    args = parser.parse_args()

    priors = load_species_priors(Path(args.dataset), args.species)

    if args.game == "public-goods":
        result = public_goods_game(priors)
    elif args.game == "ultimatum":
        result = ultimatum_game(priors)
    elif args.game == "trust":
        result = trust_game(priors)
    else:
        result = risk_choice_task(priors)

    print(f"Species: {priors.species}")
    print(f"Game: {args.game}")
    for k, v in result.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
