# Deployment Architecture

## Recommended split
1. **Data/API repo (this repo)**
   - Builds priors datasets
   - Hosts read-only API on AWS
2. **Frontend repo (Lab UI)**
   - Simulator/game UX in browser
   - Loads priors via API

This is the right separation for your plan.

## AWS target (pragmatic)
- API service: ECS Fargate (or App Runner) behind ALB
- Data artifacts: versioned in S3 (optional mirror of release snapshots)
- Frontend: separate deploy (S3 + CloudFront / Amplify / Vercel)

## Cheapest throttling path (recommended first)
- Keep current in-app rate limiting enabled (`ANIMALIA_ECON_RATE_LIMIT_PER_MINUTE`).
- Start without mandatory API keys for public read-only traffic, or use one lightweight shared key for early access.
- Deploy a single API service instance first (lowest moving parts/cost).
- Add API Gateway/WAF or distributed rate limiting only after traffic justifies it.

## Scale-up path (later)
- Move throttling to edge/API layer when you need stronger abuse controls across multiple API instances.
- Introduce stricter API key management and per-client quotas at that point.

## Why this works well
- Frontend can iterate fast independently.
- API is stable and versioned around data releases.
- Simulation compute can stay browser-side while priors remain canonical server-side.
- Observability and rate controls live with the API backend, independent of frontend deploy cadence.
