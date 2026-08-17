# GPU Worker Setup

The API does not generate images directly. It writes a job to PostgreSQL and pushes that job to Redis. A Celery worker running on the GPU server reads the job, loads FLUX, uploads images to MinIO, and updates PostgreSQL.

## 1. Server Requirements

- NVIDIA GPU with recent drivers.
- NVIDIA Container Toolkit installed if you run the worker with Docker. It is not needed for the direct Python worker path.
- Docker and Docker Compose.
- Enough disk for model weights. `black-forest-labs/FLUX.2-dev` is gated and large; the Hugging Face file list includes a 64 GB safetensors file and the model card says full inference can require more than 80 GB VRAM without offload.
- A Hugging Face account that has accepted the FLUX.2-dev model license.

## 2. Service Split

Run these services on the main server:

```text
frontend
api
postgres
redis
minio
adminer
```

Run this service on the GPU server:

```text
worker
```

The main server does not need to reach the GPU server. The GPU worker pulls work from Redis, then writes outputs back to PostgreSQL and MinIO.

Main server command:

```bash
docker compose up -d --build frontend api postgres redis minio adminer
docker compose exec api alembic -c backend/alembic.ini upgrade head
```

If you previously started the local mock worker on the main server, stop it before using the GPU worker:

```bash
docker compose stop worker
```

To intentionally run the local mock worker on the main server for development:

```bash
docker compose --profile local-worker up -d worker
```

## 3. Open Main Server Ports

The GPU server must reach these services on the main app server:

```text
PostgreSQL: 5433
Redis: 6380
MinIO: 9000
```

For production, put these on a private network or VPN instead of exposing them publicly.

## 4. Connectivity Preflight

Before downloading the model, test network connectivity.

Set these placeholders first:

```bash
export MAIN_SERVER_IP=10.218.64.88
export GPU_SERVER_IP=<your-gpu-server-ip>
export GPU_TEST_PORT=22
```

`GPU_TEST_PORT` can be `22` for SSH, or any port that is open on the GPU server. The current app design does not require the API to call the GPU server directly; this check only proves basic reachability.

Optional from the main server host to the GPU server:

```bash
nc -vz "$GPU_SERVER_IP" "$GPU_TEST_PORT"
```

Optional from the API container to the GPU server:

```bash
docker compose exec -e GPU_SERVER_IP -e GPU_TEST_PORT api python -c "import os, socket; socket.create_connection((os.environ['GPU_SERVER_IP'], int(os.environ['GPU_TEST_PORT'])), 5); print('api -> gpu ok')"
```

Optional from the frontend container to the GPU server:

```bash
docker compose exec -e GPU_SERVER_IP -e GPU_TEST_PORT frontend node -e "const net=require('net'); const s=net.createConnection(Number(process.env.GPU_TEST_PORT),process.env.GPU_SERVER_IP,()=>{console.log('frontend -> gpu ok'); s.end();}); s.setTimeout(5000); s.on('error',e=>{console.error(e.message); process.exit(1)}); s.on('timeout',()=>{console.error('timeout'); process.exit(1)});"
```

From the GPU server back to the main server services:

```bash
nc -vz "$MAIN_SERVER_IP" 5433
nc -vz "$MAIN_SERVER_IP" 6380
nc -vz "$MAIN_SERVER_IP" 9000
nc -vz "$MAIN_SERVER_IP" 8000
```

Expected result:

```text
5433 ok = GPU worker can reach PostgreSQL
6380 ok = GPU worker can reach Redis queue
9000 ok = GPU worker can upload/read MinIO objects
8000 ok = optional API reachability check
```

The required checks are `5433`, `6380`, and `9000` from the GPU server to the main server.

If `nc` is not installed on the GPU server:

```bash
python3 -c "import os, socket; socket.create_connection((os.environ['MAIN_SERVER_IP'], 5433), 5); print('postgres ok')"
python3 -c "import os, socket; socket.create_connection((os.environ['MAIN_SERVER_IP'], 6380), 5); print('redis ok')"
python3 -c "import os, socket; socket.create_connection((os.environ['MAIN_SERVER_IP'], 9000), 5); print('minio ok')"
python3 -c "import os, socket; socket.create_connection((os.environ['MAIN_SERVER_IP'], 8000), 5); print('api ok')"
```

## 5. Direct Python Worker Path

Use this path when you do not have Docker admin access on the GPU server.

On the GPU server, confirm Python and the NVIDIA driver are available:

```bash
python3 --version
nvidia-smi
git --version
```

Clone or copy this repository onto the GPU server, then enter it:

```bash
cd /path/to/Image_Generation
```

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install the GPU worker dependencies:

```bash
pip install -r worker/requirements-ml.txt
```

Create the GPU worker env file:

```bash
cp .env.gpu-worker.example .env.gpu-worker
nano .env.gpu-worker
```

Set `HF_TOKEN` and verify the main server IP values. Then load it:

```bash
set -a
source .env.gpu-worker
set +a
```

Test connectivity from the GPU server:

```bash
python3 -c "import os, socket; socket.create_connection(('10.218.64.88', 5433), 5); print('postgres ok')"
python3 -c "import os, socket; socket.create_connection(('10.218.64.88', 6380), 5); print('redis ok')"
python3 -c "import os, socket; socket.create_connection(('10.218.64.88', 9000), 5); print('minio ok')"
```

Download the model:

```bash
python scripts/download_flux2.py
```

Start the worker in the foreground:

```bash
celery -A worker.app.celery_app worker --loglevel=info -Q generation:high,generation:normal,generation:low -c 1
```

Keep this terminal open. When you click Generate in the UI, this worker should log that it received `worker.generate_image`.

For a longer-running session on a loaner server, use the helper scripts. They run the worker in a `tmux` session named `flux-worker`:

```bash
./scripts/gpu_worker_start.sh
```

Check it:

```bash
./scripts/gpu_worker_status.sh
```

Check the worker through Redis/Celery:

```bash
./scripts/gpu_worker_health.sh
```

Attach to logs:

```bash
tmux attach -t flux-worker
```

Detach from tmux with `Ctrl+b`, then `d`.

Stop it:

```bash
./scripts/gpu_worker_stop.sh
```

You can pass a non-default env file to the start script:

```bash
./scripts/gpu_worker_start.sh /path/to/.env.gpu-worker
```

## 6. Docker GPU Worker Path

Use this only if Docker is available on the GPU server.

### Create GPU Worker Env

On the GPU server, copy `.env.gpu-worker.example` to `.env.gpu-worker`:

```bash
cp .env.gpu-worker.example .env.gpu-worker
```

Then edit `.env.gpu-worker`:

```text
DATABASE_URL=postgresql+psycopg://flux:flux_local_password@MAIN_SERVER_IP:5433/flux_platform
REDIS_URL=redis://MAIN_SERVER_IP:6380/0

MINIO_ENDPOINT=http://MAIN_SERVER_IP:9000
MINIO_PUBLIC_ENDPOINT=http://MAIN_SERVER_IP:9000
MINIO_ROOT_USER=flux_minio
MINIO_ROOT_PASSWORD=flux_minio_password
MINIO_BUCKET=generations

HOST_MODEL_ROOT=./models
MODEL_ROOT=/models
GENERATION_BACKEND=flux
DEFAULT_MODEL_VERSION=flux2-dev-bf16-v1
FLUX_CONFIG_PATH=/app/model_configs/flux2.yaml
PRELOAD_MODEL_ON_STARTUP=true

HF_TOKEN=hf_your_token_here
FLUX_MODEL_ID=black-forest-labs/FLUX.2-dev
```

Replace `MAIN_SERVER_IP` with the server running `postgres`, `redis`, and `minio`.

`PRELOAD_MODEL_ON_STARTUP=true` makes the worker load FLUX when Celery starts, before the first user request. Startup takes longer, but the first generation avoids cold model loading.

### Download The Model

First accept access on Hugging Face for `black-forest-labs/FLUX.2-dev`.

Then run this on the GPU server:

```bash
docker compose -f docker-compose.gpu-worker.yml build worker
docker compose -f docker-compose.gpu-worker.yml run --rm worker python3.12 /app/scripts/download_flux2.py
```

The model downloads under:

```text
./models/black-forest-labs--FLUX.2-dev
```

The worker config uses `local_files_only: true`, so generation will use local files after download.

### Start The GPU Worker

On the GPU server:

```bash
docker compose -f docker-compose.gpu-worker.yml up -d worker
```

On the main server, keep API, frontend, Redis, Postgres, MinIO, and Adminer running:

```bash
docker compose up -d frontend api postgres redis minio adminer
```

When you click Generate in the UI, the API enqueues the job to Redis. The GPU worker pulls the job and generates the image.

## 7. Switch Back To Mock

Set this in `.env.gpu-worker`:

```text
GENERATION_BACKEND=mock
```

Then restart:

```bash
docker compose -f docker-compose.gpu-worker.yml up -d worker
```
