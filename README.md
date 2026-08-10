# FLUX.2 Self-Hosted Image Generation Platform

This repository is being built step by step into a self-hosted image generation platform around FLUX.2.

The first milestone is a full browser-to-worker platform foundation. Real model inference comes later, after the API, queue, storage, and test paths are stable.

## Current Stage

Stage 1: monorepo foundation.

Included now:

- Backend Python package skeleton.
- Worker Python package skeleton.
- Frontend package boundary for a future Next.js console.
- PostgreSQL, Redis, and MinIO placeholders in Docker Compose.
- Environment template in `.env.example`.
- Dependency manifests for backend, worker, and frontend.
- Basic Python tests that verify package imports and settings defaults.

Not included yet:

- FastAPI routes.
- Database models and migrations.
- Celery task execution.
- Real FLUX.2 inference.
- Next.js UI screens.

## Repository Layout

```text
backend/        FastAPI service, added in Stage 2
worker/         Celery and GPU worker code, added across Stages 4 and 7
frontend/       Next.js generation console, added in Stage 6
database/       SQLAlchemy models and Alembic migrations, added in Stage 3
model_configs/  FLUX.2, quality, and prompt preset YAML files
docker/         Reverse proxy and observability config
scripts/        Operational and benchmark scripts
```

The Compose services for `api`, `worker`, and `frontend` are placeholders in Stage 1. They become real services in later stages.

## Environment

Copy `.env.example` to `.env` when you are ready to run services locally:

```bash
cp .env.example .env
```

Do not commit `.env`; it contains local secrets and deployment-specific values.

Model files are expected under the ignored local `models/` directory by default once real FLUX.2 inference is added.
