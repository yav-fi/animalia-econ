# API Contract Policy (`/v1`)

## Versioning rules
- API path major version is `/v1`.
- `ANIMALIA_ECON_API_CONTRACT_VERSION` tracks schema contract revisions (default `1.0.0`).
- Every `/v1` response includes `X-API-Contract-Version` header.

## Compatibility policy
- Additive changes in `/v1` are allowed (new optional fields/endpoints).
- Breaking changes are not allowed in `/v1`.
- Breaking changes require `/v2` path and new contract version series.

## Source of truth
- Schemas are exported to `schema/api/v1/` via:
  - `make api-schema`
- CI runs contract checks to ensure schema snapshots are up to date.

## Frontend guidance
- Frontend repo should pin against `/v1` and assert `X-API-Contract-Version`.
- If contract header changes unexpectedly, frontend can fail fast and show compatibility warning.
