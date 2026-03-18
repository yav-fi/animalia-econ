from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.cli import load_entity_priors
from sim.games import public_goods_game, risk_choice_task, trust_game, ultimatum_game

TARGET_CLASSES = ["Mammalia", "Aves", "Insecta", "Actinopterygii"]


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return 0.0
    return cov / ((vx ** 0.5) * (vy ** 0.5))


def _check_range(name: str, value: float, low: float, high: float, errors: list[str]) -> None:
    if not (low <= value <= high):
        errors.append(f"{name} out of range: {value} not in [{low}, {high}]")


def run_benchmarks(dataset: Path) -> tuple[list[dict[str, object]], list[str]]:
    rows: list[dict[str, object]] = []
    errors: list[str] = []

    priors = []
    for cls in TARGET_CLASSES:
        try:
            p = load_entity_priors(dataset, entity=cls, entity_kind="taxon", rank="class")
            priors.append(p)
        except SystemExit:
            continue

    if len(priors) < 3:
        errors.append("Need at least 3 target class priors for ranking benchmarks.")
        return rows, errors

    coop_scores: list[float] = []
    pg_scores: list[float] = []
    risk_scores: list[float] = []
    rc_scores: list[float] = []

    for i, p in enumerate(priors):
        for param_name, low, high in [
            ("risk_preference", 0.0, 2.0),
            ("temporal_discount_rate", 0.0, 2.0),
            ("effort_price_elasticity", -3.0, 1.0),
            ("cooperation_propensity", 0.0, 1.0),
            ("inequity_sensitivity", 0.0, 1.0),
            ("punishment_propensity", 0.0, 1.0),
            ("tokenization_capacity", 0.0, 1.0),
        ]:
            _check_range(f"{p.entity}.{param_name}", float(getattr(p, param_name)), low, high, errors)

        random.seed(10_000 + i)
        pg = public_goods_game(p, rounds=800)
        random.seed(20_000 + i)
        ug = ultimatum_game(p, rounds=1000)
        random.seed(30_000 + i)
        tg = trust_game(p, rounds=1000)
        random.seed(40_000 + i)
        rc = risk_choice_task(p, trials=5000)

        _check_range(f"{p.entity}.public_goods.avg_contribution", float(pg["avg_contribution"]), 0.0, 10.0, errors)
        _check_range(f"{p.entity}.public_goods.expected_payoff", float(pg["expected_payoff"]), 0.0, 20.0, errors)
        _check_range(f"{p.entity}.ultimatum.avg_offer", float(ug["avg_offer"]), 0.0, 10.0, errors)
        _check_range(f"{p.entity}.ultimatum.acceptance_rate", float(ug["acceptance_rate"]), 0.0, 1.0, errors)
        _check_range(f"{p.entity}.trust.avg_sent", float(tg["avg_sent"]), 0.0, 10.0, errors)
        _check_range(f"{p.entity}.trust.avg_returned", float(tg["avg_returned"]), 0.0, 30.0, errors)
        _check_range(f"{p.entity}.trust.trust_efficiency", float(tg["trust_efficiency"]), 0.0, 3.0, errors)
        _check_range(f"{p.entity}.risk_choice.risky_choice_rate", float(rc["risky_choice_rate"]), 0.0, 1.0, errors)

        rows.append(
            {
                "entity": p.entity,
                "cooperation_propensity": round(p.cooperation_propensity, 6),
                "risk_preference": round(p.risk_preference, 6),
                "temporal_discount_rate": round(p.temporal_discount_rate, 6),
                "avg_contribution": float(pg["avg_contribution"]),
                "expected_payoff": float(pg["expected_payoff"]),
                "avg_offer": float(ug["avg_offer"]),
                "acceptance_rate": float(ug["acceptance_rate"]),
                "avg_sent": float(tg["avg_sent"]),
                "avg_returned": float(tg["avg_returned"]),
                "trust_efficiency": float(tg["trust_efficiency"]),
                "risky_choice_rate": float(rc["risky_choice_rate"]),
            }
        )
        coop_scores.append(p.cooperation_propensity)
        pg_scores.append(float(pg["avg_contribution"]))
        risk_drive = 0.25 + 0.35 * (p.risk_preference / 2.0) + 0.2 * (1.0 - p.temporal_discount_rate / 2.0)
        risk_scores.append(risk_drive)
        rc_scores.append(float(rc["risky_choice_rate"]))

    coop_corr = _pearson(coop_scores, pg_scores)
    risk_corr = _pearson(risk_scores, rc_scores)
    if coop_corr < 0.6:
        errors.append(f"Expected positive ranking: corr(cooperation_propensity, avg_contribution)={coop_corr:.3f} < 0.6")
    if risk_corr < 0.6:
        errors.append(f"Expected positive ranking: corr(risk_drive, risky_choice_rate)={risk_corr:.3f} < 0.6")

    rows.append(
        {
            "entity": "__SUMMARY__",
            "cooperation_propensity": "",
            "risk_preference": "",
            "temporal_discount_rate": "",
            "avg_contribution": "",
            "expected_payoff": "",
            "avg_offer": "",
            "acceptance_rate": "",
            "avg_sent": "",
            "avg_returned": "",
            "trust_efficiency": "",
            "risky_choice_rate": "",
            "coop_to_pg_correlation": round(coop_corr, 6),
            "risk_to_choice_correlation": round(risk_corr, 6),
            "status": "pass" if not errors else "fail",
        }
    )

    return rows, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulation realism benchmark suite for AnimaliaEcon priors.")
    parser.add_argument("--dataset", default="data/processed/animaliaecon_taxon_priors.csv")
    parser.add_argument("--out", default="data/interim/simulation_benchmark_report.csv")
    args = parser.parse_args()

    rows, errors = run_benchmarks(Path(args.dataset))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "entity",
        "cooperation_propensity",
        "risk_preference",
        "temporal_discount_rate",
        "avg_contribution",
        "expected_payoff",
        "avg_offer",
        "acceptance_rate",
        "avg_sent",
        "avg_returned",
        "trust_efficiency",
        "risky_choice_rate",
        "coop_to_pg_correlation",
        "risk_to_choice_correlation",
        "status",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Wrote simulation benchmark report: {len(rows)} -> {out_path}")
    if errors:
        print("Benchmark failed:")
        for err in errors:
            print(f"- {err}")
        raise SystemExit(1)
    print("Benchmark passed.")


if __name__ == "__main__":
    main()
