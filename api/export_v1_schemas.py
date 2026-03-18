from __future__ import annotations

import json
from pathlib import Path

from api.contracts import (
    CONTRACT_VERSION,
    ContractResponse,
    HealthResponse,
    MetaResponse,
    MetricsResponse,
    SimulateRequest,
    SimulateResponse,
    SnapshotsResponse,
    SpeciesByIdResponse,
    SpeciesRandomResponse,
    SpeciesSearchResponse,
    TaxonPriorsResponse,
)


def main() -> None:
    out_dir = Path("schema/api/v1")
    out_dir.mkdir(parents=True, exist_ok=True)

    models = {
        "health.response.json": HealthResponse,
        "meta.response.json": MetaResponse,
        "contract.response.json": ContractResponse,
        "metrics.response.json": MetricsResponse,
        "taxon_priors.response.json": TaxonPriorsResponse,
        "species_search.response.json": SpeciesSearchResponse,
        "species_by_id.response.json": SpeciesByIdResponse,
        "species_random.response.json": SpeciesRandomResponse,
        "simulate.request.json": SimulateRequest,
        "simulate.response.json": SimulateResponse,
        "snapshots.response.json": SnapshotsResponse,
    }

    for filename, model in models.items():
        schema = model.model_json_schema()
        (out_dir / filename).write_text(json.dumps(schema, indent=2), encoding="utf-8")

    index = {
        "api_version": "v1",
        "contract_version": CONTRACT_VERSION,
        "schemas": sorted(models.keys()),
    }
    (out_dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")

    print(f"Exported {len(models)} schemas -> {out_dir}")


if __name__ == "__main__":
    main()
