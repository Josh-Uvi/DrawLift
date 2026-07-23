# Implementation Plan

[Overview]
Implement fully functional frontend and backend services in the empty `frontend/` and `backend/` directories, covering TODO.md user stories US-002 through US-009.

The user's directive is to fill the empty `frontend/` and `backend/` directories with accurate, working code so that both services are fully functional and running. This spans multiple user stories from TODO.md: US-002 (Docker Compose), US-003 (linting), US-005 (FastAPI skeleton), US-006 (PostgreSQL + SQLAlchemy), US-007 (Celery + Redis), US-008 (File Upload API), and US-009 (Next.js 14 landing page with DropZone). The backend will be a FastAPI application with async PostgreSQL, Celery workers, and a file upload endpoint. The frontend will be a Next.js 14 App Router project with TypeScript, TailwindCSS, a drag-and-drop upload zone, and conversion options. A `docker-compose.yml` at the root will orchestrate all 5 services (frontend, backend, worker, postgres, redis). The implementation follows the architecture defined in README.md sections 1-7.

[Types]
Type system changes span both Python (Pydantic models, SQLAlchemy models, dataclasses) and TypeScript (interfaces mirroring backend schemas).

### Backend Types (Python)

```python
# backend/app/schemas/job.py
class JobConfig(BaseModel):
    mode: Literal["2d", "3d"] = "2d"
    dpi: int = 300
    floor_height_m: float = 3.0
    output_format: Literal["dxf", "dwg"] = "dxf"

class JobCreateResponse(BaseModel):
    job_id: str

class JobStatus(BaseModel):
    id: str
    status: Literal["pending", "queued", "processing", "completed", "failed"]
    progress: int
    step: str | None
    config: dict
    input_file: str
    output_file: str | None
    page_count: int | None
    error_msg: str | None
    created_at: datetime
    updated_at: datetime

class JobListResponse(BaseModel):
    jobs: list[JobStatus]
    total: int
```

### Frontend Types (TypeScript)

```typescript
// frontend/src/types/api.ts
type JobStatus = "pending" | "queued" | "processing" | "completed" | "failed";

interface JobConfig {
  mode: "2d" | "3d";
  dpi: number;
  floor_height_m: number;
  output_format: "dxf" | "dwg";
}

interface JobCreateResponse {
  job_id: string;
}

interface Job {
  id: string;
  status: JobStatus;
  progress: number;
  step: string | null;
  config: JobConfig;
  input_file: string;
  output_file: string | null;
  page_count: number | null;
  error_msg: string | null;
  created_at: string;
  updated_at: string;
}

interface SSEProgressEvent {
  job_id: string;
  status: JobStatus;
  progress: number;
  step: string;
}
```

[Files]
File modifications span backend Python package, frontend Next.js project, Docker configs, and root orchestration files.

### New Files — Backend

- `backend/requirements.txt` — Python dependencies (fastapi, uvicorn, sqlalchemy, asyncpg, celery, redis, pydantic-settings, python-multipart, alembic, ruff, mypy, pytest, pytest-asyncio)
- `backend/pyproject.toml` — ruff and mypy configuration
- `backend/Dockerfile` — Python 3.11-slim based, installs requirements, runs uvicorn
- `backend/app/__init__.py` — empty package init
- `backend/app/main.py` — FastAPI app instance, CORS middleware, router includes, lifespan
- `backend/app/core/__init__.py` — empty package init
- `backend/app/core/config.py` — pydantic-settings `Settings` class loading from .env
- `backend/app/core/database.py` — async SQLAlchemy engine, session factory, `get_db` dependency
- `backend/app/models/__init__.py` — empty package init
- `backend/app/models/job.py` — `Job` SQLAlchemy ORM model matching README §6 schema
- `backend/app/schemas/__init__.py` — empty package init
- `backend/app/schemas/job.py` — Pydantic request/response models
- `backend/app/api/__init__.py` — empty package init
- `backend/app/api/v1/__init__.py` — empty package init
- `backend/app/api/v1/health.py` — `GET /api/v1/health` returning `{"status": "ok"}`
- `backend/app/api/v1/jobs.py` — `POST /api/v1/jobs`, `GET /api/v1/jobs/{id}`, `GET /api/v1/jobs`
- `backend/app/api/v1/jobs_stream.py` — `GET /api/v1/jobs/{id}/stream` SSE endpoint
- `backend/app/storage/__init__.py` — empty package init
- `backend/app/storage/local.py` — `StorageBackend` ABC + `LocalStorage` implementation
- `backend/app/tasks/__init__.py` — empty package init
- `backend/app/tasks/celery_app.py` — Celery app instance with Redis broker/backend
- `backend/app/tasks/placeholder.py` — Dummy Celery task that simulates processing
- `backend/alembic.ini` — Alembic configuration pointing to `alembic/` directory
- `backend/alembic/env.py` — Alembic environment script (async)
- `backend/alembic/script.py.mako` — migration template
- `backend/alembic/versions/0001_create_jobs_table.py` — initial migration
- `backend/tests/__init__.py` — empty package init
- `backend/tests/test_health.py` — health endpoint test
- `backend/tests/conftest.py` — pytest fixtures

### New Files — Frontend

- `frontend/package.json` — Next.js 14, React 18, TypeScript, Tailwind, react-dropzone, sonner, zod
- `frontend/next.config.js` — Next.js config with API rewrites to backend
- `frontend/tsconfig.json` — TypeScript config with path aliases
- `frontend/tailwind.config.ts` — TailwindCSS configuration
- `frontend/postcss.config.js` — PostCSS config for Tailwind
- `frontend/Dockerfile` — Node 24-alpine multi-stage build
- `frontend/eslint.config.js` — ESLint flat config
- `frontend/.prettierrc` — Prettier configuration
- `frontend/src/app/layout.tsx` — Root layout with metadata, global styles
- `frontend/src/app/page.tsx` — Landing page with DropZone and ConversionOptions
- `frontend/src/app/globals.css` — Tailwind directives + global styles
- `frontend/src/app/jobs/[id]/page.tsx` — Job detail page with progress tracking
- `frontend/src/components/upload/DropZone.tsx` — Drag-and-drop file upload (react-dropzone)
- `frontend/src/components/upload/ConversionOptions.tsx` — 2D/3D toggle, DPI, floor height
- `frontend/src/components/shared/Button.tsx` — Reusable button component
- `frontend/src/components/shared/Card.tsx` — Reusable card component
- `frontend/src/components/job/ProgressTracker.tsx` — Progress bar with SSE
- `frontend/src/lib/api.ts` — Typed fetch wrapper for backend API
- `frontend/src/lib/sse.ts` — EventSource helper for progress streaming
- `frontend/src/types/api.ts` — TypeScript types mirroring backend schemas

### New Files — Root

- `docker-compose.yml` — 5 services: frontend, backend, worker, postgres, redis
- `.env.example` — All required environment variables

### Files to Delete

- `frontend/.gitkeep` — No longer needed once real files exist
- `backend/.gitkeep` — No longer needed once real files exist

[Functions]
Function modifications include new API endpoints, Celery tasks, storage adapters, and React components.

### New Functions — Backend

- `create_app()` in `backend/app/main.py` — Factory function that creates FastAPI app, adds CORS, includes routers
- `get_settings()` in `backend/app/core/config.py` — Returns cached Settings instance
- `get_db()` in `backend/app/core/database.py` — Async generator yielding SQLAlchemy sessions
- `health_check()` in `backend/app/api/v1/health.py` — Returns `{"status": "ok"}`
- `create_job()` in `backend/app/api/v1/jobs.py` — `POST /api/v1/jobs`, accepts multipart form, saves file, creates DB row, enqueues Celery task, returns `{"job_id": "..."}`
- `get_job()` in `backend/app/api/v1/jobs.py` — `GET /api/v1/jobs/{id}`, returns job status
- `list_jobs()` in `backend/app/api/v1/jobs.py` — `GET /api/v1/jobs`, paginated list
- `stream_job_progress()` in `backend/app/api/v1/jobs_stream.py` — `GET /api/v1/jobs/{id}/stream`, SSE endpoint subscribing to Redis Pub/Sub
- `save_file()` in `backend/app/storage/local.py` — Saves uploaded file to local storage directory
- `get_file_path()` in `backend/app/storage/local.py` — Returns path to stored file
- `process_job()` in `backend/app/tasks/placeholder.py` — Celery task that simulates pipeline progress, publishes to Redis Pub/Sub
- `run_placeholder_pipeline()` in `backend/app/tasks/placeholder.py` — Simulates conversion steps with sleep, updates DB progress

### New Functions — Frontend

- `uploadFile()` in `frontend/src/lib/api.ts` — POST file + config to backend, returns job_id
- `getJob()` in `frontend/src/lib/api.ts` — GET job status by ID
- `listJobs()` in `frontend/src/lib/api.ts` — GET paginated job list
- `createSSEStream()` in `frontend/src/lib/sse.ts` — Creates EventSource for job progress
- `DropZone` component in `frontend/src/components/upload/DropZone.tsx` — Drag-and-drop with PDF validation
- `ConversionOptions` component in `frontend/src/components/upload/ConversionOptions.tsx` — Mode toggle, DPI, floor height
- `ProgressTracker` component in `frontend/src/components/job/ProgressTracker.tsx` — SSE-driven progress bar
- `Button` component in `frontend/src/components/shared/Button.tsx` — Styled button
- `Card` component in `frontend/src/components/shared/Card.tsx` — Styled card container

[Classes]
Class modifications include new SQLAlchemy models, Pydantic settings, storage adapters, and Celery app.

### New Classes — Backend

- `Settings` in `backend/app/core/config.py` — pydantic-settings BaseSettings subclass with fields: `DATABASE_URL`, `REDIS_URL`, `STORAGE_PATH`, `CORS_ORIGINS`, `DEBUG`
- `Job` in `backend/app/models/job.py` — SQLAlchemy ORM model with columns: id (UUID), status, progress, step, config (JSONB), input_file, output_file, page_count, error_msg, created_at, updated_at
- `StorageBackend` in `backend/app/storage/local.py` — ABC with `save()`, `get_path()`, `delete()` abstract methods
- `LocalStorage` in `backend/app/storage/local.py` — Concrete implementation writing to local filesystem
- `celery_app` in `backend/app/tasks/celery_app.py` — Celery instance with Redis broker, JSON serializer

### New Classes — Frontend

- No classes (React functional components with hooks)

[Dependencies]
Dependency modifications include Python packages and npm packages.

### Backend (Python) — `backend/requirements.txt`

```text
fastapi==0.115.*
uvicorn[standard]==0.34.*
celery[redis]==5.*
sqlalchemy[asyncio]==2.*
asyncpg==0.30.*
pydantic-settings==2.*
python-multipart==0.0.*
alembic==1.*
ruff==0.8.*
mypy==1.*
pytest==8.*
pytest-asyncio==0.24.*
httpx==0.28.*
```

### Frontend (npm) — `frontend/package.json`

```json
{
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-dropzone": "^14.2.0",
    "sonner": "^1.4.0",
    "zod": "^3.23.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "eslint": "^8.57.0",
    "eslint-config-next": "^14.2.0",
    "prettier": "^3.2.0",
    "@types/node": "^20.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0"
  }
}
```

[Testing]
Testing approach includes backend pytest tests and frontend build verification.

### Backend Tests

- `backend/tests/test_health.py` — Tests `GET /api/v1/health` returns 200 and `{"status": "ok"}`
- `backend/tests/conftest.py` — Fixtures for async test client, test database

### Frontend Verification

- `npm run build` must succeed (Next.js production build)
- `npx eslint .` must pass
- `npx prettier --check` must pass

### Docker Verification

- `docker-compose build` must succeed for all services
- `docker-compose up` must start all 5 services without errors
- `GET http://localhost:8000/api/v1/health` returns 200
- `http://localhost:3000` renders the landing page

[Implementation Order]
Implementation sequence to minimize conflicts and ensure successful integration.

1. Create `backend/requirements.txt` and `backend/pyproject.toml` (T-010 partial)
2. Create `backend/app/` package structure: `__init__.py`, `core/`, `models/`, `schemas/`, `api/`, `storage/`, `tasks/`
3. Implement `backend/app/core/config.py` — Settings class (T-014)
4. Implement `backend/app/core/database.py` — async engine + session (T-018)
5. Implement `backend/app/models/job.py` — Job SQLAlchemy model (T-017)
6. Implement `backend/app/schemas/job.py` — Pydantic models (T-023)
7. Implement `backend/app/api/v1/health.py` — health endpoint (T-016)
8. Implement `backend/app/api/v1/jobs.py` — POST/GET endpoints (T-025, T-026)
9. Implement `backend/app/api/v1/jobs_stream.py` — SSE endpoint (T-038)
10. Implement `backend/app/storage/local.py` — storage adapter (T-024)
11. Implement `backend/app/tasks/celery_app.py` — Celery config (T-021)
12. Implement `backend/app/tasks/placeholder.py` — dummy task (T-022, T-027)
13. Implement `backend/app/main.py` — FastAPI app, CORS, routers (T-013, T-015)
14. Set up Alembic: `alembic.ini`, `alembic/env.py`, first migration (T-019)
15. Write `backend/Dockerfile` (T-007)
16. Write `backend/tests/` — test files (T-020 partial)
17. Initialise Next.js 14: `package.json`, `tsconfig.json`, configs (T-028)
18. Create `frontend/src/app/layout.tsx` and `globals.css` (T-032 partial)
19. Create `frontend/src/components/shared/Button.tsx` and `Card.tsx` (T-031)
20. Create `frontend/src/components/upload/DropZone.tsx` (T-030)
21. Create `frontend/src/components/upload/ConversionOptions.tsx` (T-033)
22. Create `frontend/src/lib/api.ts` and `frontend/src/lib/sse.ts` (T-036)
23. Create `frontend/src/types/api.ts`
24. Create `frontend/src/app/page.tsx` — landing page (T-032)
25. Create `frontend/src/app/jobs/[id]/page.tsx` — job detail (T-035)
26. Create `frontend/src/components/job/ProgressTracker.tsx` (T-037)
27. Write `frontend/Dockerfile` (T-008)
28. Write `frontend/eslint.config.js` and `.prettierrc` (T-011)
29. Write root `docker-compose.yml` (T-005)
30. Write root `.env.example` (T-006)
31. Delete `frontend/.gitkeep` and `backend/.gitkeep`
32. Install backend deps, run ruff + mypy + pytest
33. Install frontend deps, run eslint + build
34. Run `docker-compose build` and `docker-compose up` to verify all services
35. Verify health endpoint and frontend page load