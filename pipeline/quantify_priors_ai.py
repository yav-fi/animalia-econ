from __future__ import annotations

import argparse
import json
import os
import random
import urllib.error
import urllib.request

from common import clamp, read_csv, write_csv

PARAMS = [
    "risk_preference",
    "temporal_discount_rate",
    "effort_price_elasticity",
    "cooperation_propensity",
    "inequity_sensitivity",
    "punishment_propensity",
    "tokenization_capacity",
]


def default_uncertainty(source_confidence: str) -> float:
    key = source_confidence.strip().lower()
    if key == "high":
        return 0.16
    if key == "medium":
        return 0.24
    return 0.34


def class_token_bias(taxon_class: str) -> float:
    if taxon_class in {"Mammalia", "Aves", "Cephalopoda"}:
        return 0.2
    if taxon_class in {"Insecta", "Actinopterygii"}:
        return -0.05
    return 0.0


def deterministic_prior(species_row: dict[str, str], trait_row: dict[str, str]) -> dict[str, float]:
    mass = float(trait_row["mass_scaled"])
    social = float(trait_row["sociality_score"])
    diet = float(trait_row["diet_breadth_score"])
    activity = float(trait_row["activity_score"])
    habitat = float(trait_row["habitat_complexity_score"])

    risk = clamp(1.2 - 0.6 * social + 0.25 * diet + 0.2 * (1.0 - mass), 0.0, 2.0)
    discount = clamp(1.1 - 0.8 * mass + 0.25 * (1.0 - activity), 0.0, 2.0)
    effort = clamp(-1.6 + 1.1 * social + 0.6 * habitat - 0.5 * mass, -3.0, 1.0)
    coop = clamp(0.2 + 0.75 * social + 0.1 * habitat - 0.08 * risk, 0.0, 1.0)
    inequity = clamp(0.15 + 0.45 * social + 0.2 * habitat + 0.15 * mass, 0.0, 1.0)
    punishment = clamp(0.1 + 0.35 * social + 0.35 * inequity, 0.0, 1.0)
    token = clamp(0.25 + 0.5 * social + class_token_bias(species_row["class"]), 0.0, 1.0)

    return {
        "risk_preference": round(risk, 6),
        "temporal_discount_rate": round(discount, 6),
        "effort_price_elasticity": round(effort, 6),
        "cooperation_propensity": round(coop, 6),
        "inequity_sensitivity": round(inequity, 6),
        "punishment_propensity": round(punishment, 6),
        "tokenization_capacity": round(token, 6),
    }


def call_openai_prior(prompt_text: str, api_key: str, model: str) -> dict[str, float] | None:
    body = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Return only valid JSON for species economic priors with uncertainty.",
                    }
                ],
            },
            {"role": "user", "content": [{"type": "input_text", "text": prompt_text}]},
        ],
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    text_parts: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and "text" in content:
                text_parts.append(content["text"])

    if not text_parts:
        return None

    raw = "\n".join(text_parts).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not all(k in parsed for k in PARAMS + ["uncertainty_sd"]):
        return None

    return {k: float(parsed[k]) for k in PARAMS + ["uncertainty_sd"]}


def build_prompt(species_row: dict[str, str], trait_row: dict[str, str]) -> str:
    return (
        "Estimate priors for this species using only provided evidence.\n"
        f"Species: {species_row['species']}\n"
        f"Taxonomy: class={species_row['class']}, order={species_row['order']}, family={species_row['family']}\n"
        f"Traits: mass_scaled={trait_row['mass_scaled']}, sociality={trait_row['sociality_score']}, "
        f"diet_breadth={trait_row['diet_breadth_score']}, activity={trait_row['activity_score']}, "
        f"habitat_complexity={trait_row['habitat_complexity_score']}\n"
        "Return JSON with keys: risk_preference, temporal_discount_rate, effort_price_elasticity, "
        "cooperation_propensity, inequity_sensitivity, punishment_propensity, tokenization_capacity, uncertainty_sd."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate species priors with optional AI refinement.")
    parser.add_argument("--species", required=True, help="Path to species seed CSV.")
    parser.add_argument("--traits", required=True, help="Path to normalized trait CSV.")
    parser.add_argument("--out", required=True, help="Output CSV path.")
    parser.add_argument("--use-ai", action="store_true", help="Enable OpenAI API refinement if credentials exist.")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5-mini"), help="OpenAI model name.")
    parser.add_argument("--seed", type=int, default=7, help="RNG seed for deterministic jitter.")
    args = parser.parse_args()

    random.seed(args.seed)

    species_rows = read_csv(args.species)
    trait_rows = {r["species"]: r for r in read_csv(args.traits)}

    api_key = os.getenv("OPENAI_API_KEY")
    use_ai = args.use_ai and bool(api_key)

    out_rows: list[dict[str, object]] = []
    for species_row in species_rows:
        species = species_row["species"]
        trait_row = trait_rows.get(species)
        if not trait_row:
            continue

        base = deterministic_prior(species_row, trait_row)
        uncertainty = default_uncertainty(trait_row["source_confidence"])

        provenance_type = "imputed_trait"
        source_model = "deterministic_heuristic_v0"

        if use_ai and api_key:
            prompt = build_prompt(species_row, trait_row)
            ai_vals = call_openai_prior(prompt, api_key, args.model)
            if ai_vals:
                for p in PARAMS:
                    # Blend AI estimate with deterministic baseline for stability in bootstrap phase.
                    base[p] = round(0.65 * base[p] + 0.35 * clamp(ai_vals[p], -3.0, 2.0), 6)
                uncertainty = round(clamp(ai_vals["uncertainty_sd"], 0.01, 1.0), 6)
                provenance_type = "ai_estimated"
                source_model = args.model

        jitter = random.uniform(-0.02, 0.02)
        uncertainty = round(clamp(uncertainty + jitter, 0.01, 1.0), 6)

        out_rows.append(
            {
                "species": species,
                **base,
                "uncertainty_sd": uncertainty,
                "provenance_type": provenance_type,
                "source_model": source_model,
            }
        )

    fields = ["species", *PARAMS, "uncertainty_sd", "provenance_type", "source_model"]
    write_csv(args.out, out_rows, fields)
    print(f"Wrote prior estimates: {len(out_rows)} -> {args.out}")


if __name__ == "__main__":
    main()
