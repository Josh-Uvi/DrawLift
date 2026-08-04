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
| `DWG_CONVERTER_COMMAND` | Optional external DWG conversion command template. |
| `CORS_ORIGINS` | Allowed frontend origins. |
| `NEXT_PUBLIC_API_URL` | Browser-visible API base URL. |

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

Celery Beat runs cleanup based on `STORAGE_TTL_DAYS`. Cleanup archives job metadata and removes expired local files.

For local Make runtime files:

```bash
make clean-local-runtime
```

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Frontend cannot reach API | Confirm `NEXT_PUBLIC_API_URL` and backend port 8000. |
| Jobs stay pending | Check worker logs and Redis health. |
| Downloads 404/409 | Confirm job is completed and output artifact exists. |
| Page previews missing | Confirm parser produced `pages/page_0001.png` and `page_count`. |
| DWG output missing | Confirm `output_format` and `DWG_CONVERTER_COMMAND`. |
| Hybrid path issues | Confirm shared `LOCAL_STORAGE_DIR` and `LOCAL_MODELS_DIR`. |
