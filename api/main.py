from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.contracts import (
    API_VERSION,
    CONTRACT_VERSION,
    ContractResponse,
    DatasetStats,
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
from api.observability import ApiMetrics
from api.security import FixedWindowRateLimiter, parse_api_keys
from api.service import (
    dataset_stats,
    get_species,
    get_species_by_id,
    get_taxon,
    list_snapshot_versions,
    list_taxa,
    random_species,
    row_to_priors,
    search_species,
    simulate,
)

logger = logging.getLogger("animalia.api")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

RATE_LIMIT_PER_MINUTE = int(os.getenv("ANIMALIA_ECON_RATE_LIMIT_PER_MINUTE", "240"))
API_KEYS = parse_api_keys(os.getenv("ANIMALIA_ECON_API_KEYS", ""))

rate_limiter = FixedWindowRateLimiter(limit_per_minute=RATE_LIMIT_PER_MINUTE)
metrics = ApiMetrics()


def _parse_origins() -> list[str]:
    raw = os.getenv("ANIMALIA_ECON_CORS_ORIGINS", "*").strip()
    if raw == "*":
        return ["*"]
    return [item.strip() for item in raw.split(",") if item.strip()]


def _client_identity(request: Request) -> str:
    key = request.headers.get("x-api-key", "").strip()
    if key:
        return f"key:{key[:10]}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def _auth_required(path: str) -> bool:
    if path in {"/health"}:
        return False
    return path.startswith("/v1")


app = FastAPI(title="AnimaliaEcon API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_rate_observability_middleware(request: Request, call_next):
    started = time.perf_counter()
    request_id = str(uuid.uuid4())
    path = request.url.path

    if _auth_required(path):
        if API_KEYS:
            presented = request.headers.get("x-api-key", "").strip()
            if presented not in API_KEYS:
                latency_ms = (time.perf_counter() - started) * 1000.0
                metrics.record(path=path, status_code=401, latency_ms=latency_ms)
                response = JSONResponse(status_code=401, content={"detail": "Unauthorized"})
                response.headers["X-Request-Id"] = request_id
                response.headers["X-API-Contract-Version"] = CONTRACT_VERSION
                return response

        decision = rate_limiter.check(_client_identity(request))
        if not decision.allowed:
            latency_ms = (time.perf_counter() - started) * 1000.0
            metrics.record(path=path, status_code=429, latency_ms=latency_ms)
            response = JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
            response.headers["Retry-After"] = str(decision.retry_after_seconds)
            response.headers["X-RateLimit-Limit-Minute"] = str(RATE_LIMIT_PER_MINUTE)
            response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
            response.headers["X-Request-Id"] = request_id
            response.headers["X-API-Contract-Version"] = CONTRACT_VERSION
            return response

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        latency_ms = (time.perf_counter() - started) * 1000.0
        metrics.record(path=path, status_code=500, latency_ms=latency_ms)
        logger.exception("api_request_failed path=%s request_id=%s", path, request_id)
        raise

    latency_ms = (time.perf_counter() - started) * 1000.0
    metrics.record(path=path, status_code=status_code, latency_ms=latency_ms)

    response.headers["X-Request-Id"] = request_id
    response.headers["X-API-Contract-Version"] = CONTRACT_VERSION
    response.headers["X-RateLimit-Limit-Minute"] = str(RATE_LIMIT_PER_MINUTE)

    log_payload = {
        "path": path,
        "method": request.method,
        "status": status_code,
        "latency_ms": round(latency_ms, 3),
        "request_id": request_id,
    }
    logger.info("api_request %s", log_payload)

    return response


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/v1/meta", response_model=MetaResponse)
def meta(dataset_version: str | None = Query(default=None)) -> MetaResponse:
    return MetaResponse(
        service="animalia-econ-api",
        api_version=API_VERSION,
        contract_version=CONTRACT_VERSION,
        stats=DatasetStats(**dataset_stats(dataset_version=dataset_version)),
    )


@app.get("/v1/contract", response_model=ContractResponse)
def contract() -> ContractResponse:
    return ContractResponse(
        api_version=API_VERSION,
        contract_version=CONTRACT_VERSION,
        policy="Additive changes in /v1 are non-breaking. Breaking changes require /v2.",
        schema_dir="schema/api/v1",
    )


@app.get("/v1/metrics", response_model=MetricsResponse)
def api_metrics() -> MetricsResponse:
    snap = metrics.snapshot()
    return MetricsResponse(**snap)


@app.get("/v1/snapshots", response_model=SnapshotsResponse)
def snapshots() -> SnapshotsResponse:
    current = dataset_stats()["dataset_version"]
    return SnapshotsResponse(
        current_dataset_version=current,
        available_versions=list_snapshot_versions(),
    )


@app.get("/v1/taxon-priors", response_model=TaxonPriorsResponse)
def taxon_priors(
    rank: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    dataset_version: str | None = Query(default=None),
) -> TaxonPriorsResponse:
    try:
        rows = list_taxa(rank=rank, taxon_query=q, limit=limit, offset=offset, dataset_version=dataset_version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TaxonPriorsResponse(count=len(rows), rows=rows)


@app.get("/v1/taxon-priors/{rank}/{taxon}", response_model=dict[str, str])
def taxon_prior(rank: str, taxon: str, dataset_version: str | None = Query(default=None)) -> dict[str, str]:
    try:
        row = get_taxon(rank, taxon, dataset_version=dataset_version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Taxon prior not found")
    return row


@app.get("/v1/species-priors/{species}", response_model=dict[str, str])
def species_prior(
    species: str,
    dataset: Literal["inherited", "observed"] = "inherited",
    dataset_version: str | None = Query(default=None),
) -> dict[str, str]:
    try:
        row = get_species(species, dataset=dataset, dataset_version=dataset_version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Species prior not found")
    return row


@app.get("/v1/species/search", response_model=SpeciesSearchResponse)
def species_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=5, ge=1, le=25),
    dataset: Literal["inherited", "observed"] = "inherited",
    dataset_version: str | None = Query(default=None),
) -> SpeciesSearchResponse:
    try:
        rows = search_species(query=q, dataset=dataset, limit=limit, dataset_version=dataset_version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SpeciesSearchResponse(count=len(rows), rows=rows)


@app.get("/v1/species/by-id/{species_id}", response_model=SpeciesByIdResponse)
def species_by_id(species_id: str, dataset_version: str | None = Query(default=None)) -> SpeciesByIdResponse:
    try:
        payload = get_species_by_id(species_id, dataset_version_override=dataset_version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not payload:
        raise HTTPException(status_code=404, detail="Species row not found")
    return SpeciesByIdResponse(**payload)


@app.get("/v1/species/random", response_model=SpeciesRandomResponse)
def species_random(
    bucket: Literal["mammal", "bird", "insect", "fish"] | None = Query(default=None),
    dataset: Literal["inherited", "observed"] = "inherited",
    dataset_version: str | None = Query(default=None),
) -> SpeciesRandomResponse:
    try:
        payload = random_species(dataset=dataset, bucket=bucket, dataset_version=dataset_version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SpeciesRandomResponse(**payload)


@app.post("/v1/simulate", response_model=SimulateResponse)
def simulate_endpoint(req: SimulateRequest) -> SimulateResponse:
    if req.entity_kind == "taxon":
        if not req.rank:
            raise HTTPException(status_code=400, detail="`rank` is required for taxon simulations")
        try:
            row = get_taxon(req.rank, req.entity_name, dataset_version=req.dataset_version)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not row:
            raise HTTPException(status_code=404, detail="Taxon prior not found")
        label = f"{row.get('rank', req.rank)}={row.get('taxon', req.entity_name)}"
    else:
        try:
            row = get_species(req.entity_name, dataset=req.species_dataset, dataset_version=req.dataset_version)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not row:
            raise HTTPException(status_code=404, detail="Species prior not found")
        label = row.get("species", req.entity_name)

    priors = row_to_priors(row, label=label)
    result = simulate(req.game, priors, rounds=req.rounds, trials=req.trials)

    return SimulateResponse(
        entity_kind=req.entity_kind,
        entity=label,
        game=req.game,
        result={k: float(v) for k, v in result.items()},
    )


@app.get("/v1/snapshots/{dataset_version}/meta", response_model=MetaResponse)
def snapshot_meta(dataset_version: str) -> MetaResponse:
    try:
        stats = dataset_stats(dataset_version=dataset_version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MetaResponse(
        service="animalia-econ-api",
        api_version=API_VERSION,
        contract_version=CONTRACT_VERSION,
        stats=DatasetStats(**stats),
    )


@app.get("/v1/snapshots/{dataset_version}/taxon-priors", response_model=TaxonPriorsResponse)
def snapshot_taxon_priors(
    dataset_version: str,
    rank: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> TaxonPriorsResponse:
    try:
        rows = list_taxa(rank=rank, taxon_query=q, limit=limit, offset=offset, dataset_version=dataset_version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TaxonPriorsResponse(count=len(rows), rows=rows)


@app.get("/v1/snapshots/{dataset_version}/species/search", response_model=SpeciesSearchResponse)
def snapshot_species_search(
    dataset_version: str,
    q: str = Query(..., min_length=1),
    limit: int = Query(default=5, ge=1, le=25),
    dataset: Literal["inherited", "observed"] = "inherited",
) -> SpeciesSearchResponse:
    try:
        rows = search_species(query=q, dataset=dataset, limit=limit, dataset_version=dataset_version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SpeciesSearchResponse(count=len(rows), rows=rows)


@app.post("/v1/snapshots/{dataset_version}/simulate", response_model=SimulateResponse)
def snapshot_simulate(dataset_version: str, req: SimulateRequest) -> SimulateResponse:
    # Compatibility across Pydantic v2 (`model_copy`) and v1 (`copy`).
    if hasattr(req, "model_copy"):
        req_with_version = req.model_copy(update={"dataset_version": dataset_version})
    else:
        req_with_version = req.copy(update={"dataset_version": dataset_version})
    return simulate_endpoint(req_with_version)
