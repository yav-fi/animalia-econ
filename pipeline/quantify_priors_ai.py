from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from common import ProgressPrinter, clamp, read_csv, utc_now_iso, write_csv

PARAMS = [
    "risk_preference",
    "temporal_discount_rate",
    "effort_price_elasticity",
    "cooperation_propensity",
    "inequity_sensitivity",
    "punishment_propensity",
    "tokenization_capacity",
]

PROMPT_VERSION = "v2"
DEFAULT_WATERFALL_RANKS = ["family", "order", "class", "phylum"]
OUTPUT_FIELDS = [
    "species",
    *PARAMS,
    "uncertainty_sd",
    "provenance_type",
    "source_model",
    "ai_prompt_version",
    "ai_rationale_hash",
    "evidence_sources",
    "extraction_notes",
    "row_confidence_score",
    "deterministic_anchor_rank",
    "deterministic_anchor_taxon",
    "species_adjust_weight",
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


def deterministic_prior_from_values(
    mass: float,
    social: float,
    diet: float,
    activity: float,
    habitat: float,
    taxon_class: str,
) -> dict[str, float]:
    mass = clamp(mass, 0.0, 1.0)
    social = clamp(social, 0.0, 1.0)
    diet = clamp(diet, 0.0, 1.0)
    activity = clamp(activity, 0.0, 1.0)
    habitat = clamp(habitat, 0.0, 1.0)

    risk = clamp(1.2 - 0.6 * social + 0.25 * diet + 0.2 * (1.0 - mass), 0.0, 2.0)
    discount = clamp(1.1 - 0.8 * mass + 0.25 * (1.0 - activity), 0.0, 2.0)
    effort = clamp(-1.6 + 1.1 * social + 0.6 * habitat - 0.5 * mass, -3.0, 1.0)
    coop = clamp(0.2 + 0.75 * social + 0.1 * habitat - 0.08 * risk, 0.0, 1.0)
    inequity = clamp(0.15 + 0.45 * social + 0.2 * habitat + 0.15 * mass, 0.0, 1.0)
    punishment = clamp(0.1 + 0.35 * social + 0.35 * inequity, 0.0, 1.0)
    token = clamp(0.25 + 0.5 * social + class_token_bias(taxon_class), 0.0, 1.0)

    return {
        "risk_preference": round(risk, 6),
        "temporal_discount_rate": round(discount, 6),
        "effort_price_elasticity": round(effort, 6),
        "cooperation_propensity": round(coop, 6),
        "inequity_sensitivity": round(inequity, 6),
        "punishment_propensity": round(punishment, 6),
        "tokenization_capacity": round(token, 6),
    }


def deterministic_prior(species_row: dict[str, str], trait_row: dict[str, str]) -> dict[str, float]:
    return deterministic_prior_from_values(
        mass=float(trait_row["mass_scaled"]),
        social=float(trait_row["sociality_score"]),
        diet=float(trait_row["diet_breadth_score"]),
        activity=float(trait_row["activity_score"]),
        habitat=float(trait_row["habitat_complexity_score"]),
        taxon_class=species_row.get("class", ""),
    )


def _taxon_aggregate_priors(
    species_rows: list[dict[str, str]],
    trait_rows: dict[str, dict[str, str]],
    ranks: list[str],
) -> dict[tuple[str, str], dict[str, float]]:
    grouped_traits: dict[tuple[str, str], list[dict[str, float]]] = defaultdict(list)
    class_counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)

    for species_row in species_rows:
        species = species_row.get("species", "").strip()
        trait = trait_rows.get(species)
        if not trait:
            continue
        try:
            trait_vector = {
                "mass_scaled": float(trait["mass_scaled"]),
                "sociality_score": float(trait["sociality_score"]),
                "diet_breadth_score": float(trait["diet_breadth_score"]),
                "activity_score": float(trait["activity_score"]),
                "habitat_complexity_score": float(trait["habitat_complexity_score"]),
            }
        except (KeyError, ValueError):
            continue

        for rank in ranks:
            taxon = species_row.get(rank, "").strip()
            if not taxon:
                continue
            key = (rank, taxon)
            grouped_traits[key].append(trait_vector)
            taxon_class = species_row.get("class", "").strip()
            if taxon_class:
                class_counts[key][taxon_class] += 1

    out: dict[tuple[str, str], dict[str, float]] = {}
    for (rank, taxon), vectors in grouped_traits.items():
        n = len(vectors)
        if n == 0:
            continue
        mean_mass = sum(v["mass_scaled"] for v in vectors) / n
        mean_social = sum(v["sociality_score"] for v in vectors) / n
        mean_diet = sum(v["diet_breadth_score"] for v in vectors) / n
        mean_activity = sum(v["activity_score"] for v in vectors) / n
        mean_habitat = sum(v["habitat_complexity_score"] for v in vectors) / n

        if rank == "class":
            dominant_class = taxon
        else:
            most_common = class_counts[(rank, taxon)].most_common(1)
            dominant_class = most_common[0][0] if most_common else ""
        out[(rank, taxon)] = deterministic_prior_from_values(
            mass=mean_mass,
            social=mean_social,
            diet=mean_diet,
            activity=mean_activity,
            habitat=mean_habitat,
            taxon_class=dominant_class,
        )

    return out


def _resolve_waterfall_anchor(
    species_row: dict[str, str],
    taxon_priors: dict[tuple[str, str], dict[str, float]],
    waterfall_ranks: list[str],
) -> tuple[str, str, dict[str, float] | None]:
    for rank in waterfall_ranks:
        taxon = species_row.get(rank, "").strip()
        if not taxon:
            continue
        prior = taxon_priors.get((rank, taxon))
        if prior:
            return rank, taxon, prior
    return "", "", None


def _blend_anchor_with_species(
    anchor_prior: dict[str, float],
    species_prior: dict[str, float],
    species_adjust_weight: float,
) -> dict[str, float]:
    w = clamp(species_adjust_weight, 0.0, 1.0)
    out: dict[str, float] = {}
    for p in PARAMS:
        low, high = _bounds(p)
        out[p] = round(clamp((1.0 - w) * anchor_prior[p] + w * species_prior[p], low, high), 6)
    return out


def _extract_json_payload(text: str) -> dict[str, Any] | None:
    raw = text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _parse_prior_proposal(value: str) -> dict[str, float]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    out: dict[str, float] = {}
    for p in PARAMS:
        if p not in payload:
            continue
        try:
            out[p] = float(payload[p])
        except (TypeError, ValueError):
            continue
    return out


def _apply_behavior_prior_proposal(base: dict[str, float], behavior_row: dict[str, str] | None) -> dict[str, float]:
    if not behavior_row:
        return base
    proposal = _parse_prior_proposal(behavior_row.get("prior_proposal_json", ""))
    if not proposal:
        return base

    try:
        evidence_confidence = clamp(float(behavior_row.get("evidence_confidence", "0.0") or 0.0), 0.0, 1.0)
    except ValueError:
        evidence_confidence = 0.0
    weight = 0.35 * evidence_confidence
    out = dict(base)
    for p in PARAMS:
        if p not in proposal:
            continue
        low, high = _bounds(p)
        out[p] = round(clamp(out[p] + weight * proposal[p], low, high), 6)
    return out


def call_bedrock_prior(prompt_text: str, model_id: str, aws_region: str) -> dict[str, float] | None:
    try:
        import boto3
        from botocore.config import Config
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        return None

    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=aws_region,
            config=Config(connect_timeout=8, read_timeout=35, retries={"max_attempts": 2, "mode": "standard"}),
        )
        response = client.converse(
            modelId=model_id,
            system=[
                {
                    "text": (
                        "Return only compact JSON with numeric keys: risk_preference, "
                        "temporal_discount_rate, effort_price_elasticity, cooperation_propensity, "
                        "inequity_sensitivity, punishment_propensity, tokenization_capacity, uncertainty_sd."
                    )
                }
            ],
            messages=[{"role": "user", "content": [{"text": prompt_text}]}],
            inferenceConfig={"temperature": 0.1, "maxTokens": 500},
        )
    except (BotoCoreError, ClientError, Exception):
        return None

    parts = response.get("output", {}).get("message", {}).get("content", [])
    joined = "\n".join(part.get("text", "") for part in parts if "text" in part).strip()
    if not joined:
        return None

    parsed = _extract_json_payload(joined)
    if not parsed:
        return None

    required = PARAMS + ["uncertainty_sd"]
    if not all(k in parsed for k in required):
        return None

    try:
        return {k: float(parsed[k]) for k in required}
    except (TypeError, ValueError):
        return None


def call_bedrock_prior_with_retries(
    prompt_text: str,
    model_id: str,
    aws_region: str,
    max_retries: int,
    base_backoff_seconds: float,
) -> tuple[dict[str, float] | None, str | None]:
    for attempt in range(max_retries + 1):
        values = call_bedrock_prior(prompt_text, model_id=model_id, aws_region=aws_region)
        if values is not None:
            return values, None

        if attempt < max_retries:
            sleep_seconds = base_backoff_seconds * (2**attempt)
            time.sleep(sleep_seconds)

    return None, f"bedrock_call_failed_after_{max_retries + 1}_attempts"


def build_prompt(
    species_row: dict[str, str],
    trait_row: dict[str, str],
    anchor_rank: str,
    anchor_taxon: str,
    anchor_prior: dict[str, float] | None,
    behavior_row: dict[str, str] | None,
) -> str:
    anchor_line = "Taxon anchor: none"
    if anchor_prior:
        anchor_json = json.dumps(anchor_prior, sort_keys=True, separators=(",", ":"))
        anchor_line = f"Taxon anchor: {anchor_rank}={anchor_taxon}; deterministic_anchor_prior={anchor_json}"
    behavior_line = "Behavior evidence: unavailable"
    if behavior_row:
        behavior_line = (
            "Behavior evidence: "
            f"task_family={behavior_row.get('task_family', '')}; "
            f"evidence_confidence={behavior_row.get('evidence_confidence', '')}; "
            f"source={behavior_row.get('source_name', '')}; "
            f"proposal={behavior_row.get('prior_proposal_json', '')}"
        )

    return (
        "Estimate economic-game priors using only provided structured evidence.\n"
        f"Prompt version: {PROMPT_VERSION}\n"
        "Entity kind: species\n"
        f"Species: {species_row['species']}\n"
        f"Taxonomy: phylum={species_row['phylum']}, class={species_row['class']}, order={species_row['order']}, family={species_row['family']}\n"
        f"Traits: mass_scaled={trait_row['mass_scaled']}, sociality={trait_row['sociality_score']}, "
        f"diet_breadth={trait_row['diet_breadth_score']}, activity={trait_row['activity_score']}, "
        f"habitat_complexity={trait_row['habitat_complexity_score']}\n"
        f"{anchor_line}\n"
        f"{behavior_line}\n"
        "Respect bounds: risk_preference[0,2], temporal_discount_rate[0,2], effort_price_elasticity[-3,1], "
        "cooperation_propensity[0,1], inequity_sensitivity[0,1], punishment_propensity[0,1], tokenization_capacity[0,1], uncertainty_sd[0.01,1]."
    )


def _bounds(param: str) -> tuple[float, float]:
    if param == "effort_price_elasticity":
        return -3.0, 1.0
    if param in {"risk_preference", "temporal_discount_rate"}:
        return 0.0, 2.0
    return 0.0, 1.0


def _signature_for(
    species_row: dict[str, str],
    trait_row: dict[str, str],
    use_ai: bool,
    model_id: str,
    anchor_rank: str,
    anchor_taxon: str,
    anchor_prior: dict[str, float] | None,
    species_adjust_weight: float,
    behavior_row: dict[str, str] | None,
) -> str:
    payload = {
        "prompt_version": PROMPT_VERSION,
        "use_ai": use_ai,
        "model": model_id if use_ai else "none",
        "species_adjust_weight": round(species_adjust_weight, 6),
        "species": species_row.get("species", ""),
        "taxonomy": {
            "phylum": species_row.get("phylum", ""),
            "class": species_row.get("class", ""),
            "order": species_row.get("order", ""),
            "family": species_row.get("family", ""),
        },
        "deterministic_anchor": {
            "rank": anchor_rank,
            "taxon": anchor_taxon,
            "prior": anchor_prior or {},
        },
        "behavior_evidence": {
            "task_family": (behavior_row or {}).get("task_family", ""),
            "evidence_confidence": (behavior_row or {}).get("evidence_confidence", ""),
            "source_name": (behavior_row or {}).get("source_name", ""),
            "proposal": (behavior_row or {}).get("prior_proposal_json", ""),
        },
        "traits": {
            "mass_scaled": trait_row.get("mass_scaled", ""),
            "sociality_score": trait_row.get("sociality_score", ""),
            "diet_breadth_score": trait_row.get("diet_breadth_score", ""),
            "activity_score": trait_row.get("activity_score", ""),
            "habitat_complexity_score": trait_row.get("habitat_complexity_score", ""),
            "source_confidence": trait_row.get("source_confidence", ""),
        },
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _has_required_row_fields(row: dict[str, str]) -> bool:
    needed = set(OUTPUT_FIELDS)
    return needed.issubset(set(row.keys()))


def _row_confidence_score(
    species_row: dict[str, str],
    trait_row: dict[str, str],
    behavior_row: dict[str, str] | None,
) -> float:
    source_conf = trait_row.get("source_confidence", "").strip().lower()
    base = {"high": 0.92, "medium": 0.78, "low": 0.62}.get(source_conf, 0.55)
    candidate_score = species_row.get("candidate_confidence_score", "")
    candidate_val = None
    if candidate_score:
        try:
            candidate_val = float(candidate_score)
        except ValueError:
            candidate_val = None
    behavior_conf = None
    if behavior_row:
        try:
            behavior_conf = float(behavior_row.get("evidence_confidence", "") or 0.0)
        except ValueError:
            behavior_conf = None

    score = base
    if candidate_val is not None:
        score = 0.7 * score + 0.3 * clamp(candidate_val, 0.0, 1.0)
    if behavior_conf is not None:
        score = 0.75 * score + 0.25 * clamp(behavior_conf, 0.0, 1.0)

    return round(clamp(score, 0.0, 1.0), 6)


def _rationale_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _default_signature_path(out_path: str) -> str:
    p = Path(out_path)
    return str(p.with_name(f"{p.stem}_signatures.csv"))


def _default_error_log_path(out_path: str) -> str:
    p = Path(out_path)
    return str(p.with_name(f"{p.stem}_ai_errors.csv"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate priors with optional AWS Bedrock refinement.")
    parser.add_argument("--species", required=True, help="Path to species seed CSV.")
    parser.add_argument("--traits", required=True, help="Path to normalized trait CSV.")
    parser.add_argument("--behavior", default="", help="Optional behavior evidence CSV path.")
    parser.add_argument("--out", required=True, help="Output CSV path.")
    parser.add_argument("--use-ai", action="store_true", help="Enable AWS Bedrock refinement if credentials exist.")
    parser.add_argument(
        "--update-mode",
        choices=["incremental", "full"],
        default="full",
        help="`full` recalculates all rows. `incremental` reuses unchanged rows using signatures.",
    )
    parser.add_argument(
        "--signature-out",
        default="",
        help="Optional signatures CSV path. Defaults to <out>_signatures.csv.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
        help="Bedrock model ID (for example Claude or Nova model IDs).",
    )
    parser.add_argument(
        "--aws-region",
        default=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
        help="AWS region for Bedrock runtime.",
    )
    parser.add_argument("--ai-max-retries", type=int, default=2, help="Max Bedrock retries per species.")
    parser.add_argument("--ai-base-backoff-seconds", type=float, default=1.0, help="Base backoff seconds for retries.")
    parser.add_argument("--error-log", default="", help="Optional AI error log CSV path.")
    parser.add_argument(
        "--species-adjust-weight",
        type=float,
        default=0.2,
        help="Blend weight for species residual around taxon waterfall anchor (0..1).",
    )
    parser.add_argument(
        "--waterfall-ranks",
        default=",".join(DEFAULT_WATERFALL_RANKS),
        help="Comma-separated deterministic waterfall ranks from nearest to broadest (default: family,order,class,phylum).",
    )
    parser.add_argument("--seed", type=int, default=7, help="RNG seed for deterministic jitter.")
    args = parser.parse_args()

    random.seed(args.seed)

    signature_out = args.signature_out or _default_signature_path(args.out)
    error_log_path = args.error_log or _default_error_log_path(args.out)

    species_rows = read_csv(args.species)
    trait_rows = {r["species"]: r for r in read_csv(args.traits)}
    behavior_rows = {r["species"]: r for r in read_csv(args.behavior)} if args.behavior and Path(args.behavior).exists() else {}
    waterfall_ranks = [r.strip() for r in args.waterfall_ranks.split(",") if r.strip()]
    if not waterfall_ranks:
        waterfall_ranks = list(DEFAULT_WATERFALL_RANKS)
    species_adjust_weight = clamp(args.species_adjust_weight, 0.0, 1.0)
    taxon_anchor_priors = _taxon_aggregate_priors(species_rows, trait_rows, ranks=waterfall_ranks)

    existing_rows: dict[str, dict[str, str]] = {}
    existing_signatures: dict[str, str] = {}

    if args.update_mode == "incremental":
        if Path(args.out).exists():
            existing_rows = {r["species"]: r for r in read_csv(args.out) if r.get("species")}
        if Path(signature_out).exists():
            existing_signatures = {
                r["species"]: r["signature"]
                for r in read_csv(signature_out)
                if r.get("species") and r.get("signature")
            }

    out_rows: list[dict[str, object]] = []
    sig_rows: list[dict[str, str]] = []
    reused = 0
    recalculated = 0
    ai_calls = 0
    ai_failures = 0
    error_rows: list[dict[str, str]] = []
    progress = ProgressPrinter(total=len(species_rows), label="quantify_priors")

    for species_row in species_rows:
        species = species_row["species"]
        trait_row = trait_rows.get(species)
        if not trait_row:
            progress.tick()
            continue

        anchor_rank, anchor_taxon, anchor_prior = _resolve_waterfall_anchor(
            species_row,
            taxon_anchor_priors,
            waterfall_ranks=waterfall_ranks,
        )
        signature = _signature_for(
            species_row,
            trait_row,
            use_ai=args.use_ai,
            model_id=args.model,
            anchor_rank=anchor_rank,
            anchor_taxon=anchor_taxon,
            anchor_prior=anchor_prior,
            species_adjust_weight=species_adjust_weight,
            behavior_row=behavior_rows.get(species),
        )
        existing_sig = existing_signatures.get(species)
        existing_row = existing_rows.get(species)

        if args.update_mode == "incremental" and existing_sig == signature and existing_row and _has_required_row_fields(existing_row):
            out_rows.append({k: existing_row[k] for k in OUTPUT_FIELDS})
            sig_rows.append(
                {
                    "species": species,
                    "signature": signature,
                    "prompt_version": PROMPT_VERSION,
                    "updated_at": utc_now_iso(),
                    "action": "reused",
                }
            )
            reused += 1
            progress.tick()
            continue

        recalculated += 1

        species_level_base = deterministic_prior(species_row, trait_row)
        if anchor_prior:
            base = _blend_anchor_with_species(
                anchor_prior,
                species_level_base,
                species_adjust_weight=species_adjust_weight,
            )
        else:
            base = species_level_base

        behavior_row = behavior_rows.get(species)
        base = _apply_behavior_prior_proposal(base, behavior_row)
        uncertainty = default_uncertainty(trait_row["source_confidence"])
        row_confidence = _row_confidence_score(species_row, trait_row, behavior_row)
        if behavior_row:
            try:
                behavior_conf = clamp(float(behavior_row.get("evidence_confidence", "") or 0.0), 0.0, 1.0)
                uncertainty = round(clamp(uncertainty * (1.0 - 0.18 * behavior_conf), 0.01, 1.0), 6)
            except ValueError:
                pass

        provenance_type = "imputed_trait"
        source_model = "deterministic_taxon_waterfall_v1"
        if anchor_prior:
            extraction_notes = (
                "Deterministic prior estimated from taxon waterfall anchor blended with species trait residual; "
                f"anchor={anchor_rank}:{anchor_taxon}, species_adjust_weight={species_adjust_weight:.3f}."
            )
            evidence_sources = "seed_traits_normalized|taxonomy_backbone|taxon_waterfall_anchor"
        else:
            extraction_notes = "Deterministic prior estimated from species traits (no taxon waterfall anchor available)."
            evidence_sources = "seed_traits_normalized|taxonomy_backbone"
        if behavior_row:
            evidence_sources = f"{evidence_sources}|behavior_evidence:{behavior_row.get('source_name', 'unknown')}"
            extraction_notes = f"{extraction_notes} Behavior evidence proposal applied."
        rationale_payload: dict[str, Any] = {
            "species": species,
            "prompt_version": PROMPT_VERSION,
            "mode": "deterministic",
            "species_level_base": species_level_base,
            "anchor_rank": anchor_rank,
            "anchor_taxon": anchor_taxon,
            "anchor_prior": anchor_prior or {},
            "species_adjust_weight": species_adjust_weight,
            "behavior_evidence": behavior_row or {},
            "base": base,
        }

        if args.use_ai:
            prompt = build_prompt(species_row, trait_row, anchor_rank, anchor_taxon, anchor_prior, behavior_row)
            ai_vals, err = call_bedrock_prior_with_retries(
                prompt_text=prompt,
                model_id=args.model,
                aws_region=args.aws_region,
                max_retries=max(args.ai_max_retries, 0),
                base_backoff_seconds=max(args.ai_base_backoff_seconds, 0.05),
            )
            if ai_vals:
                ai_calls += 1
                for p in PARAMS:
                    low, high = _bounds(p)
                    base[p] = round(0.65 * base[p] + 0.35 * clamp(ai_vals[p], low, high), 6)
                uncertainty = round(clamp(ai_vals["uncertainty_sd"], 0.01, 1.0), 6)
                provenance_type = "ai_estimated"
                source_model = args.model
                extraction_notes = (
                    "Bayesian prior blended from deterministic taxon-waterfall baseline and Bedrock JSON estimate."
                )
                evidence_sources = f"{evidence_sources}|bedrock:{args.model}"
                rationale_payload = {
                    "species": species,
                    "prompt_version": PROMPT_VERSION,
                    "mode": "ai_blend",
                    "prompt": prompt,
                    "ai_values": ai_vals,
                    "blended_base": base,
                }
            elif err:
                ai_failures += 1
                error_rows.append(
                    {
                        "species": species,
                        "error_code": err,
                        "model": args.model,
                        "aws_region": args.aws_region,
                        "max_retries": str(args.ai_max_retries),
                        "timestamp": utc_now_iso(),
                    }
                )
                rationale_payload = {
                    "species": species,
                    "prompt_version": PROMPT_VERSION,
                    "mode": "ai_fallback",
                    "error": err,
                    "deterministic_base": base,
                }

        jitter = random.uniform(-0.02, 0.02)
        uncertainty = round(clamp(uncertainty + jitter, 0.01, 1.0), 6)
        ai_rationale_hash = _rationale_hash(rationale_payload)

        out_rows.append(
            {
                "species": species,
                **base,
                "uncertainty_sd": uncertainty,
                "provenance_type": provenance_type,
                "source_model": source_model,
                "ai_prompt_version": PROMPT_VERSION,
                "ai_rationale_hash": ai_rationale_hash,
                "evidence_sources": evidence_sources,
                "extraction_notes": extraction_notes,
                "row_confidence_score": row_confidence,
                "deterministic_anchor_rank": anchor_rank,
                "deterministic_anchor_taxon": anchor_taxon,
                "species_adjust_weight": round(species_adjust_weight, 6),
            }
        )
        sig_rows.append(
            {
                "species": species,
                "signature": signature,
                "prompt_version": PROMPT_VERSION,
                "updated_at": utc_now_iso(),
                "action": "recalculated",
            }
        )
        progress.tick()
    progress.finish()

    write_csv(args.out, out_rows, OUTPUT_FIELDS)
    write_csv(signature_out, sig_rows, ["species", "signature", "prompt_version", "updated_at", "action"])
    if error_rows:
        write_csv(
            error_log_path,
            error_rows,
            ["species", "error_code", "model", "aws_region", "max_retries", "timestamp"],
        )

    print(f"Wrote prior estimates: {len(out_rows)} -> {args.out}")
    print(f"Wrote signatures: {len(sig_rows)} -> {signature_out}")
    if error_rows:
        print(f"Wrote AI error log: {len(error_rows)} -> {error_log_path}")
    print(
        "Update mode: "
        f"{args.update_mode}; reused={reused}; recalculated={recalculated}; "
        f"ai_calls={ai_calls}; ai_failures={ai_failures}"
    )


if __name__ == "__main__":
    main()
