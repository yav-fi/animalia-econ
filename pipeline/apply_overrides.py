from __future__ import annotations

import argparse
import csv
from pathlib import Path

from common import ProgressPrinter, clamp, read_csv, write_csv

PARAMS = [
    "risk_preference",
    "temporal_discount_rate",
    "effort_price_elasticity",
    "cooperation_propensity",
    "inequity_sensitivity",
    "punishment_propensity",
    "tokenization_capacity",
]


def _bounds(param: str) -> tuple[float, float]:
    if param == "effort_price_elasticity":
        return -3.0, 1.0
    if param in {"risk_preference", "temporal_discount_rate"}:
        return 0.0, 2.0
    if param in {"cooperation_propensity", "inequity_sensitivity", "punishment_propensity", "tokenization_capacity"}:
        return 0.0, 1.0
    if param == "uncertainty_sd":
        return 0.01, 1.0
    return float("-inf"), float("inf")


def _active(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _coerce_value(param: str, value: str) -> str:
    if param in PARAMS or param == "uncertainty_sd":
        low, high = _bounds(param)
        val = clamp(float(value), low, high)
        return str(round(val, 6))
    return str(value)


def _recompute_intervals(row: dict[str, str]) -> None:
    if "uncertainty_sd" not in row:
        return
    sd = float(row["uncertainty_sd"])
    for p in PARAMS:
        if p not in row:
            continue
        val = float(row[p])
        low_b, high_b = _bounds(p)
        lo = clamp(val - 1.96 * sd, low_b, high_b)
        hi = clamp(val + 1.96 * sd, low_b, high_b)
        lo_k = f"{p}_lower"
        hi_k = f"{p}_upper"
        if lo_k in row:
            row[lo_k] = str(round(lo, 6))
        if hi_k in row:
            row[hi_k] = str(round(hi, 6))


def _load_overrides(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip comment rows or blank rows.
            first_val = next(iter(row.values()), "")
            if str(first_val).strip().startswith("#"):
                continue
            rows.append({k: (v or "").strip() for k, v in row.items()})
    return rows


def _key_for_row(entity_kind: str, row: dict[str, str]) -> tuple[str, str]:
    if entity_kind == "species":
        return ("species", row.get("species", "").strip())
    rank = row.get("rank", "").strip()
    taxon = row.get("taxon", "").strip()
    return (rank, taxon)


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply manual overrides to species or taxon priors.")
    parser.add_argument("--entity-kind", choices=["species", "taxon"], required=True)
    parser.add_argument("--in", dest="in_path", required=True, help="Input CSV to patch.")
    parser.add_argument("--overrides", required=True, help="Overrides CSV path.")
    parser.add_argument("--out", required=True, help="Patched CSV output path.")
    parser.add_argument("--audit-out", required=True, help="Audit log CSV output path.")
    args = parser.parse_args()

    in_rows = read_csv(args.in_path)
    overrides_path = Path(args.overrides)

    if not overrides_path.exists():
        # No override file yet: pass-through and empty audit.
        write_csv(args.out, in_rows, list(in_rows[0].keys()) if in_rows else [])
        write_csv(args.audit_out, [], ["entity_kind", "entity", "param", "old_value", "new_value", "note"])
        print(f"No overrides file found. Passed through {len(in_rows)} rows -> {args.out}")
        return

    overrides = [r for r in _load_overrides(overrides_path) if _active(r.get("active", "false"))]

    row_map: dict[tuple[str, str], dict[str, str]] = {}
    for row in in_rows:
        row_map[_key_for_row(args.entity_kind, row)] = row

    audit_rows: list[dict[str, str]] = []
    applied = 0

    progress = ProgressPrinter(total=len(overrides), label=f"apply_overrides:{args.entity_kind}")
    for ov in overrides:
        if args.entity_kind == "species":
            key = ("species", ov.get("species", ""))
            entity_label = ov.get("species", "")
        else:
            key = (ov.get("rank", ""), ov.get("taxon", ""))
            entity_label = f"{ov.get('rank', '')}:{ov.get('taxon', '')}"

        row = row_map.get(key)
        if not row:
            progress.tick()
            continue

        param = ov.get("param", "")
        value = ov.get("value", "")
        note = ov.get("note", "")

        if not param or value == "":
            progress.tick()
            continue

        old_value = row.get(param, "")

        if param in PARAMS or param == "uncertainty_sd":
            new_value = _coerce_value(param, value)
            row[param] = new_value
            _recompute_intervals(row)
        elif param in {"provenance_type", "source_model"}:
            row[param] = value
        else:
            progress.tick()
            continue

        applied += 1
        audit_rows.append(
            {
                "entity_kind": args.entity_kind,
                "entity": entity_label,
                "param": param,
                "old_value": str(old_value),
                "new_value": str(row.get(param, "")),
                "note": note,
            }
        )
        progress.tick()
    progress.finish()

    fields = list(in_rows[0].keys()) if in_rows else []
    write_csv(args.out, in_rows, fields)
    write_csv(args.audit_out, audit_rows, ["entity_kind", "entity", "param", "old_value", "new_value", "note"])
    print(f"Applied overrides: {applied} -> {args.out}")
    print(f"Audit log rows: {len(audit_rows)} -> {args.audit_out}")


if __name__ == "__main__":
    main()
