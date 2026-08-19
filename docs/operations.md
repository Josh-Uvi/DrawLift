# Operations

This document summarizes local operations for DrawLift.

## Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Important variables:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy async PostgreSQL URL. |
| `REDIS_URL` | Redis URL for Celery and Pub/Sub. |
| `STORAGE_PATH` | Root for uploaded/generated files. |
| `STORAGE_TTL_DAYS` | Cleanup/archive threshold. |
| `MODELS_PATH` | ONNX/model cache directory. |
| `SEGMENTER_MODEL_PATH` | Optional explicit path to the segmentation ONNX model. |
| `SEGMENTER_MODEL_URL` | Optional http(s) URL used to auto-download the segmentation model when the file is missing. |
| `SEGMENTER_MODEL_INPUT_SIZE` | ONNX model input resolution side length in pixels (default `128`). Lower = less memory. |
| `DWG_CONVERTER_COMMAND` | Optional external DWG conversion command template. |
| `CORS_ORIGINS` | Allowed frontend origins. |
| `NEXT_PUBLIC_API_URL` | Browser-visible API base URL. |
| `JOB_STALE_TIMEOUT_SECONDS` | Seconds a job may stay in `processing` before being marked `failed` (default 300). |
| `WORKER_MEM_LIMIT` | Docker memory limit for the Celery worker (default `4g`). |
| `WORKER_MEMSWAP_LIMIT` | Docker memory+swap limit for the worker (default `6g`). |

## Docker workflow

```bash
make docker-up
make docker-migrate
make docker-ps
make docker-logs
make docker-down
```

Start optional DWG profile:

```bash
make docker-up-dwg
```

This profile now builds GNU LibreDWG from source and exports `/opt/libredwg`
through a named volume. The runtime services mount that volume read-only and
default `DWG_CONVERTER_COMMAND` to `dwgwrite {input} {output}`.

## ML model provisioning

`backend/models/semantic_segmenter.onnx` ships a small reference model so the
`ml` segmenter works out of the box. To (re)provision it, or to swap in trained
weights, use:

```bash
make download-model                       # provision the reference model
make download-model MODEL_URL=<url>       # download trained weights instead
make validate-model                       # validate model contract + configured input size
```

Every provisioned artifact is validated (exists, <100 MB, CPU-only ONNX
Runtime load, 5-class decodable output). `make validate-model` also verifies
that the configured `SEGMENTER_MODEL_INPUT_SIZE` matches the model's declared
input dimensions. Invalid downloads are removed.

`SEGMENTER_MODEL_PATH` and `SEGMENTER_MODEL_URL` are set by default in
`.env.example` and `docker-compose.yml`; the URL is used as an auto-download
fallback when the model file is missing (e.g. a fresh Docker models volume).
Celery workers preload the configured model once per process at startup
(`worker_process_init`), so misconfiguration surfaces in worker logs
immediately.

## Hybrid local workflow

Install dependencies first:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd ../frontend
npm install
```

Start services:

```bash
make local-up
```

The hybrid workflow runs frontend/backend on the host and PostgreSQL, Redis, and worker in Docker. It bind-mounts `backend/storage` and `backend/models` so host API and Docker worker share files.

Useful commands:

```bash
make local-status
make logs-backend
make logs-frontend
make logs-worker
make local-down
```

## Database migrations

Docker:

```bash
make docker-migrate
```

Hybrid host backend:

```bash
make local-migrate
```

Manual:

```bash
cd backend
alembic upgrade head
```

## Tests and checks

Backend:

```bash
cd backend
ruff check .
ruff format --check .
mypy app/
pytest
```

Frontend:

```bash
cd frontend
npm run lint
npm run format:check
npm run build
```

Pre-commit:

```bash
pre-commit install
pre-commit run --all-files
```

## Cleanup

Celery Beat runs two periodic cleanup tasks:

1. **Expired-job cleanup** (daily) — archives jobs and removes local files older than `STORAGE_TTL_DAYS`.
2. **Stale-job recovery** (every 5 minutes) — marks jobs stuck in `processing` for longer than `JOB_STALE_TIMEOUT_SECONDS` as `failed`. This handles the case where a worker is killed (e.g. OOM SIGKILL) before it can write a failure status.

For local Make runtime files:

```bash
make clean-local-runtime
```

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Frontend cannot reach API | Confirm `NEXT_PUBLIC_API_URL` and backend port 8000. |
| Jobs stay pending | Confirm the worker is running (`make local-status` or `docker-compose ps`) and check `make logs-worker` for `Received unregistered task` errors. Task modules must be listed in the Celery `include` setting in `backend/app/tasks/celery_app.py`. |
| No progress updates in UI | Conversion progress is emitted by the worker, not the API. Check `make logs-worker` (or `docker-compose logs worker`). The job page also polls the API every 3 seconds as a fallback, so confirm the backend is reachable. |
| Downloads 404/409 | Confirm job is completed and output artifact exists. |
| Page previews missing | Confirm parser produced `pages/page_0001.png` and `page_count`. |
| DWG output missing | Confirm `output_format` and `DWG_CONVERTER_COMMAND`. |
| Hybrid path issues | Confirm shared `LOCAL_STORAGE_DIR` and `LOCAL_MODELS_DIR`. |
| Worker killed by SIGKILL (OOM) | The ONNX segmentation model + image pipeline can exceed the container memory limit. Check `docker-compose logs worker` for `signal 9 (SIGKILL)` / `WorkerLostError`. Increase `WORKER_MEM_LIMIT` / `WORKER_MEMSWAP_LIMIT` in `.env`, or reduce PDF DPI. The stale-job sweeper will eventually mark the orphaned job as `failed`. |
| Jobs stuck in `processing` | A worker may have been killed before writing a failure status. The stale-job sweeper (every 5 min) will transition these to `failed` after `JOB_STALE_TIMEOUT_SECONDS`. Verify the worker is running and check logs for OOM or errors. |

## Logging

| Log target | Contents |
| --- | --- |
| `make logs-backend` / `docker-compose logs backend` | FastAPI HTTP requests and API errors. |
| `make logs-worker` / `docker-compose logs worker` | Celery task lifecycle and conversion progress lines from `app.tasks.placeholder` (starting, step count, success/failure). |
| `make logs-frontend` | Next.js dev server output. |

Conversion status is logged by the worker, not the API. Watching only backend logs will not show conversion progress.
