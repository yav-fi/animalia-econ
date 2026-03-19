# AnimaliaEcon API

Read-only FastAPI service for dataset access and simulation utilities.

## Base URLs
- Local: `http://localhost:8000`
- Deployed (AnimaliaEcon Lambda URL): `https://rjyk2byic5rizunv6t4osudxpu0cnzgx.lambda-url.us-east-1.on.aws`

## Run locally
```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
# or:
make api-dev
```

## Deploy backend API (Lambda URL)
```bash
# Default:
make deploy-api

# Optional overrides:
make deploy-api LAMBDA_FUNCTION=AnimaliaEconApi DEPLOY_REGION=us-east-1 DEPLOY_BUCKET=<bucket-name> DEPLOY_PREFIX=deployments/animaliaeconapi
```

What it does:
- Builds a Lambda zip with API code, simulation module, processed datasets, release snapshots, and `/v1` schema artifacts.
- Stages the zip to S3, updates the Lambda function code, waits for completion, then prints the function URL and verify command.
- Default deploy dependencies are pinned for Lambda-compatible packaging from non-Linux hosts (`fastapi==0.95.2`, `pydantic==1.10.24`, `mangum==0.17.0`).

## Configuration
- `ANIMALIA_ECON_API_KEYS`: comma-separated API keys. If empty, auth is disabled.
- `ANIMALIA_ECON_RATE_LIMIT_PER_MINUTE`: fixed-window request limit per client key/IP (default `240`).
- `ANIMALIA_ECON_CORS_ORIGINS`: comma-separated origins, or `*`.
- `ANIMALIA_ECON_API_CONTRACT_VERSION`: contract header value (default `1.0.0`).
- `ANIMALIA_ECON_TAXON_DATASET`: override taxon CSV path.
- `ANIMALIA_ECON_SPECIES_INHERITED`: override inherited species CSV path.
- `ANIMALIA_ECON_SPECIES_OBSERVED`: override observed species CSV path.
- `ANIMALIA_ECON_RELEASES_ROOT`: release snapshot root for pinned datasets (default `releases/datasets`).

## Endpoints
- `GET /health`
- `GET /v1/meta?dataset_version=latest|<version>`
- `GET /v1/contract`
- `GET /v1/metrics`
- `GET /v1/snapshots` (list immutable versions)
- `GET /v1/taxon-priors?rank=class&q=mamm&limit=50&offset=0&dataset_version=<version>`
- `GET /v1/taxon-priors/{rank}/{taxon}?dataset_version=<version>`
- `GET /v1/species-priors/{species}?dataset=inherited|observed&dataset_version=<version>`
- `GET /v1/species/search?q=chimp&limit=5&dataset=inherited|observed&dataset_version=<version>`
- `GET /v1/species/by-id/{id}` (ID carries dataset version)
- `GET /v1/species/random?bucket=mammal|bird|insect|fish&dataset=inherited|observed&dataset_version=<version>`
- `POST /v1/simulate`
- `GET /v1/snapshots/{dataset_version}/meta`
- `GET /v1/snapshots/{dataset_version}/taxon-priors`
- `GET /v1/snapshots/{dataset_version}/species/search`
- `POST /v1/snapshots/{dataset_version}/simulate`

## Operational behavior
- Auth header: `X-API-Key` (only required when keys are configured).
- Rate-limited responses return `429` and `Retry-After`.
- Response headers include:
  - `X-Request-Id`
  - `X-API-Contract-Version`
  - `X-RateLimit-Limit-Minute`
- Contract schemas are snapshotted under `schema/api/v1/`.
- `dataset_version` is included in stats, species search hits, random species, and by-id payloads for reproducibility.
