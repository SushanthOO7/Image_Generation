# FLUX.2 Self-Hosted Image Generation Platform

This repository is being built step by step into a self-hosted image generation platform around FLUX.2.

The first milestone is a full browser-to-worker platform foundation. Real model inference comes later, after the API, queue, storage, and app paths are stable.

## Current Stage

Stage 13 foundation: GPU worker setup path for real FLUX inference with mock mode still enabled by default.

Included now:

- Backend Python package skeleton.
- Worker Python package skeleton.
- Runnable Next.js frontend on `FRONTEND_PORT`.
- Browser verification console for API health, prompt submission, polling, and MinIO image display.
- UI controls for cancelling active jobs and saving thumbs up/down feedback.
- JWT login/register flow with password hashes stored in PostgreSQL.
- Authenticated generation and feedback tied to `users.id`.
- Redis-backed per-user generation rate limit.
- Per-user concurrent generation limit.
- User plans for free/pro/team generation limits.
- Monthly generation quota accounting per user and plan.
- User-managed API keys for programmatic generation access.
- Frontend API key creation, one-time secret reveal, copy, and revoke controls.
- FastAPI health and mock generation endpoints backed by PostgreSQL.
- SQLAlchemy models for users, generation jobs, outputs, and feedback.
- Alembic migration for the initial database schema.
- Redis-backed Celery queue for generation jobs.
- Worker service that advances mock jobs from `QUEUED` to `GENERATING` to `COMPLETED`.
- MinIO object storage for generated image files.
- Adminer database browser for inspecting PostgreSQL tables.
- Mock WebP image, final image, and thumbnail uploads under `generations/YYYY/MM/{job_id}/`.
- PostgreSQL output rows now store MinIO object keys.
- Worker generation backend abstraction.
- Optional FLUX backend path controlled by `GENERATION_BACKEND=flux`.
- FLUX model config in `model_configs/flux2.yaml`.
- Prompt style presets in `model_configs/presets.yaml`.
- Quality presets in `model_configs/quality.yaml`.
- Backend job planning for expanded prompts, aspect-ratio dimensions, steps, guidance, and candidate counts.
- Worker generation of multiple mock candidates based on quality preset candidate count.
- MinIO uploads for `candidate-{n}.webp`, selected `final.webp`, and `thumbnail.webp`.
- PostgreSQL output rows for every candidate plus the selected final image.
- Frontend display for planned dimensions, candidate count, expanded prompt, and candidate thumbnails.
- Authenticated `POST /v1/generations/{job_id}/select-output` endpoint for changing the selected output.
- Candidate thumbnails can be clicked in the UI to update the selected image.
- Authenticated `GET /v1/generations` endpoint for listing recent jobs.
- Frontend history panel for reopening previous generations and inspecting their selected outputs.
- Alembic migration for `generation_jobs.archived_at`.
- Authenticated `POST /v1/generations/{job_id}/archive` endpoint for hiding completed, failed, or cancelled jobs from history.
- Frontend archive control for history rows.
- GPU worker Compose file in `docker-compose.gpu-worker.yml`.
- GPU worker Dockerfile in `worker/Dockerfile.gpu`.
- FLUX.2 download helper in `scripts/download_flux2.py`.
- Remote GPU worker setup guide in `docs/GPU_WORKER_SETUP.md`.
- Direct Python GPU worker path uses the same `.env.gpu-worker` file as Docker.
- Direct Python GPU worker preflight for CUDA visibility and model config checks.
- Direct FLUX runtime validation script for one real GPU generation before Celery startup.
- FLUX generator now uses planned job width, height, steps, and guidance.
- Optional ML dependency file in `worker/requirements-ml.txt`.
- Dependency manifests for backend, worker, and frontend.

Not included yet:

- Billing integration.

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

## Run The App

Validate the Compose file:

```bash
scripts/ops.sh compose-config
```

Start the stack:

```bash
docker compose up -d --build frontend api postgres redis minio adminer
```

Apply database migrations:

```bash
scripts/ops.sh migrate
```

Open the frontend at the value of `FRONTEND_PUBLIC_URL`, usually `http://localhost:3001`.

From the frontend you can verify:

- Register or login.
- API health.
- Active job and limit counters.
- Monthly quota remaining for the signed-in user.
- API key management for programmatic generation access.
- Prompt submission.
- Active job cancellation.
- Redis/Celery job progress.
- PostgreSQL-backed job status.
- Planned dimensions and candidate count from backend.
- Style-based expanded prompt returned by the generation status API.
- Candidate thumbnail strip and selected final output.
- Manual selected-output changes after a job completes.
- Recent generation history after login and after each completed job.
- History cleanup by archiving old terminal jobs.
- MinIO final image display.
- Feedback writes into `generation_feedback`.

Check the API:

```bash
curl http://localhost:8000/internal/health
```

Submit a mock generation job:

```bash
curl -X POST http://localhost:8000/v1/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"prompt":"A futuristic city at sunset","aspect_ratio":"16:9","quality":"ultra","style":"cinematic"}'
```

The API expands the prompt, stores the planned dimensions and candidate count, then enqueues the job in Redis. The Celery worker updates status and creates a mock output row in PostgreSQL.

The completed job response returns a MinIO URL for the selected output image.

Watch worker logs:

```bash
docker compose logs -f worker
```

For local mock generation on the main server, start the worker profile:

```bash
docker compose --profile local-worker up -d worker
```

Check the active worker backend:

```bash
docker compose exec worker python -c "from worker.app.settings import load_worker_settings; from worker.app.health import worker_health; print(worker_health(load_worker_settings()))"
```

Create an API key after logging in:

```bash
curl -X POST http://localhost:8000/v1/me/api-keys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt_token>" \
  -d '{"name":"local script"}'
```

Use the returned `flux_sk_...` secret as a bearer token for generation requests:

```bash
curl -X POST http://localhost:8000/v1/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <flux_sk_api_key>" \
  -d '{"prompt":"A cinematic product photograph of an ice sculpture","quality":"fast"}'
```

Admins can move a user between built-in plans:

```bash
curl -X PATCH http://localhost:8000/v1/admin/users/<user_id>/plan \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin_jwt_token>" \
  -d '{"plan":"pro"}'
```

To attempt real FLUX inference, follow:

```text
docs/GPU_WORKER_SETUP.md
```

For the direct Python worker path, copy `.env.gpu-worker.example` to
`.env.gpu-worker`, edit the main server addresses, then run:

```bash
python scripts/gpu_worker_preflight.py
python scripts/validate_flux_runtime.py --width 512 --height 512 --steps 4
python scripts/validate_ranker.py --backend clip
```

The same operational checks are available through:

```bash
scripts/ops.sh check
scripts/ops.sh gpu-preflight
scripts/ops.sh gpu-validate --width 512 --height 512 --steps 4
scripts/ops.sh worker-start
```

To require a real smoke generation before the direct Python worker starts, set this in `.env.gpu-worker`:

```text
FLUX_VALIDATE_RUNTIME_ON_START=true
```

At a high level, install the optional ML dependencies in the GPU worker image, mount model files under `models/`, then set:

```text
GENERATION_BACKEND=flux
```

Open MinIO:

```text
http://localhost:9001
```

Use `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` from `.env`.

Open Adminer for PostgreSQL:

```text
http://localhost:8080
```

Use:

```text
System: PostgreSQL
Server: postgres
Username: flux
Password: flux_local_password
Database: flux_platform
```

Use `postgres` exactly for the Server field. `localhost` points at the Adminer container itself, not the database.

## Environment

Copy `.env.example` to `.env` when you are ready to run services locally:

```bash
cp .env.example .env
```

Do not commit `.env`; it contains local secrets and deployment-specific values.

Model files are expected under the ignored local `models/` directory by default once real FLUX.2 inference is added.
