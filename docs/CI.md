# CI Workflow

GitHub Actions workflow: `.github/workflows/ci.yml`

## What CI checks
1. Build pipeline outputs (`make pipeline`)
2. Validate processed outputs (`make validate-data`)
3. Run unit/integration tests (`make test`)
4. Export and verify API contract snapshots (`make api-schema`, `make contract-check`)
5. Smoke-test dataset release flow (`pipeline/release_dataset.py` to `/tmp`)

This keeps data outputs, API contracts, and release mechanics aligned on every PR/push.
