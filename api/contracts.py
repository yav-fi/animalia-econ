from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field

API_VERSION = "v1"
CONTRACT_VERSION = os.getenv("ANIMALIA_ECON_API_CONTRACT_VERSION", "1.0.0")


class DatasetStats(BaseModel):
    dataset_version: str
    available_versions: list[str]
    taxon_rows: int
    species_inherited_rows: int
    species_observed_rows: int


class HealthResponse(BaseModel):
    status: str


class MetaResponse(BaseModel):
    service: str
    api_version: str
    contract_version: str
    stats: DatasetStats


class TaxonPriorsResponse(BaseModel):
    count: int
    rows: list[dict[str, str]]


class SpeciesSearchHit(BaseModel):
    id: str
    dataset: str
    dataset_version: str
    label: str
    species: str
    common_name: str
    bucket: str


class SpeciesSearchResponse(BaseModel):
    count: int
    rows: list[SpeciesSearchHit]


class SpeciesByIdResponse(BaseModel):
    id: str
    dataset: str
    dataset_version: str
    label: str
    row: dict[str, str]


class SpeciesRandomResponse(BaseModel):
    id: str
    dataset: str
    dataset_version: str
    label: str
    requested_bucket: str | None
    matched_bucket: bool
    row: dict[str, str]


class SimulateRequest(BaseModel):
    game: Literal["public-goods", "ultimatum", "trust", "risk-choice"]
    entity_kind: Literal["taxon", "species"] = "taxon"
    entity_name: str = Field(..., min_length=1)
    rank: str | None = None
    species_dataset: Literal["inherited", "observed"] = "inherited"
    dataset_version: str | None = None
    rounds: int | None = Field(default=None, ge=1, le=2000)
    trials: int | None = Field(default=None, ge=1, le=100000)


class SimulateResponse(BaseModel):
    entity_kind: str
    entity: str
    game: str
    result: dict[str, float]


class ContractResponse(BaseModel):
    api_version: str
    contract_version: str
    policy: str
    schema_dir: str


class MetricsResponse(BaseModel):
    total_requests: int
    total_errors: int
    avg_latency_ms: float
    path_counts: dict[str, int]
    status_counts: dict[str, int]


class SnapshotsResponse(BaseModel):
    current_dataset_version: str
    available_versions: list[str]
