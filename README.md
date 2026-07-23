# AI File Converter — Architecture Drawings to DWG

A web application that converts architecture drawings (PDFs) into editable 2D or 3D CAD models in DWG (and DXF) format. Built with a modern, decoupled architecture that separates the user-facing experience (Next.js) from the compute-heavy image processing and ML pipeline (Python/FastAPI).

> **Status:** Implementation in progress — Phase 1 (scaffolding & upload flow) is complete and running, and Phase 2 pipeline infrastructure is in review. All 5 Docker services (frontend, backend, worker, postgres, redis) are operational. See the phased roadmap at the bottom for what's next.
>
> 📋 **Looking for the execution plan?** See [TODO.md](./TODO.md) — a complete breakdown of 28 user stories and 92 actionable tasks managed as **GitHub Issues** via the `gh` CLI and the GitHub MCP server.

---

## 1. Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| **Frontend** | Next.js 14 (App Router) + TypeScript + TailwindCSS | React ecosystem, SSR-ready, built-in API proxy, excellent DX |
| **Backend API** | **Python 3.11 + FastAPI** | Unmatched ecosystem for image processing (OpenCV, PIL), ML (PyTorch/ONNX), and CAD libraries (ezdxf, libredwg). Node.js is weak in this domain. |
| **Async Workers** | Celery + Redis | PDF→DWG conversion takes 30s–5min; must run out-of-band to avoid HTTP timeouts. |
| **Database** | PostgreSQL 16 | Stores job metadata, config, and history. JSONB for flexible per-job settings. |
| **File Storage** | Local FS (dev) / S3-compatible (prod) | Large binary blobs (PDFs/DWGs) abstracted behind a storage adapter. |
| **Containerization** | Docker + Docker Compose | Reproducible dev env with 5 services: frontend, API, Celery worker, Redis, PostgreSQL. |
| **ML Inference** | ONNX Runtime (production), PyTorch (training) | CPU-friendly inference, easy model swaps. |

---

## 2. High-Level System Architecture

```
┌──────────────┐     HTTP/REST      ┌──────────────┐     Redis Queue     ┌───────────────┐
│   Next.js    │ ─────────────────► │   FastAPI    │ ──────────────────► │    Celery     │
│   Frontend   │ ◄───────────────── │   Backend    │ ◄────────────────── │    Worker     │
│  (port 3000) │   JSON + SSE       │  (port 8000) │   Result Backend   │  (1–N procs)  │
└──────────────┘                    └──────┬───────┘                     └───────┬───────┘
                                          │                                     │
                                          ▼                                     ▼
                                   ┌──────────────┐                     ┌──────────────┐
                                   │  PostgreSQL  │                     │ File Store   │
                                   │  (metadata)  │                     │ (PDFs/DWGs)  │
                                   └──────────────┘                     └──────────────┘
```

### End-to-end Flow
1. User uploads a PDF via the Next.js UI → `POST /api/v1/jobs` to FastAPI.
2. FastAPI validates, stores the PDF, creates a DB record (`status: pending`), enqueues a Celery task, returns `job_id`.
3. Frontend subscribes to `/api/v1/jobs/{id}/stream` (SSE) for real-time progress.
4. Celery worker runs the **conversion pipeline** (§3).
5. Worker updates DB and stores the generated DWG/DXF.
6. User downloads via `/api/v1/jobs/{id}/download`.

---

## 3. Conversion Pipeline (Core IP)

The pipeline runs inside the Celery worker and is composed of pluggable steps. Each step receives and returns a `PipelineContext`.

```
   PDF Input
       │
       ▼
[1] PDF Parsing       PyMuPDF extracts each page as a high-res image (default 300 DPI)
       │
       ▼
[2] Preprocessing     Grayscale → denoise → adaptive threshold → deskew (OpenCV)
       │
       ▼
[3] Semantic          ML segmentation classifies pixels into:
    Segmentation      Walls · Doors · Windows · Rooms · Dimensions · Text
                      Options: YOLOv8-seg · U-Net · SAM (fine-tuned on floor plans)
       │
       ▼
[4] Vectorization     Contour detection → polygon simplification → classify as
                      line / arc / circle. Generate parametric primitives:
                      wall = (start, end, thickness)
       │
       ▼
[5] 3D Extrusion      (if 3D mode) Extrude walls by floor height metadata
   [optional]         or user-specified height. Add slabs and openings.
       │
       ▼
[6] DWG/DXF Writer    Write primitives to DWG/DXF (see §9 trade-off on DXF-first)
       │
       ▼
  Output File
```

### Reference: Pipeline Context

```python
@dataclass
class PipelineContext:
    job_id: str
    input_path: Path
    page_images: list[Path]            # populated by Step 1
    preprocessed: list[np.ndarray]     # populated by Step 2
    masks: dict[str, np.ndarray]       # populated by Step 3 (one per class)
    primitives: list[Primitive]        # populated by Step 4
    output_path: Path | None           # populated by Step 6
    config: dict                       # user-provided options
```

---

## 4. Frontend Structure (Next.js)

```
frontend/src/
├── app/
│   ├── globals.css               # TailwindCSS global styles
│   ├── layout.tsx                # Root layout, metadata, Toaster
│   ├── page.tsx                  # Landing / upload page
│   └── jobs/[id]/page.tsx        # Job detail: live progress via SSE
│
├── components/
│   ├── upload/
│   │   ├── DropZone.tsx          # Drag & drop (react-dropzone)
│   │   └── ConversionOptions.tsx # 2D/3D toggle, DPI, floor height, format
│   ├── job/
│   │   └── ProgressTracker.tsx   # Stepper: Uploaded → Processing → Completed
│   └── shared/
│       ├── Button.tsx
│       └── Card.tsx
│
├── lib/
│   ├── api.ts                    # Typed fetch wrapper (uploadFile, getJob, listJobs)
│   └── sse.ts                    # EventSource helper for progress streaming
│
└── types/
    └── api.ts                    # Mirrors backend Pydantic schemas
```

### Key UX States
- **Uploading** — Progress bar with file name & size.
- **Queued** — "Waiting in queue, position #3".
- **Processing** — Step-by-step progress: PDF Parsing → Segmentation → Vectorization → DWG.
- **Completed** — Side-by-side preview (original page vs. generated wireframe), download links.
- **Failed** — Error message with retry button.

---

## 5. REST API Design (FastAPI)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/jobs` | Upload PDF + config (multipart/form-data) → returns `{ job_id }` |
| `GET` | `/api/v1/jobs/{id}` | Get job status, progress (0–100), current step |
| `GET` | `/api/v1/jobs/{id}/stream` | **SSE** — real-time progress updates |
| `GET` | `/api/v1/jobs/{id}/pages/{n}` | Extracted page image (for preview) |
| `GET` | `/api/v1/jobs/{id}/download` | Download resulting DWG/DXF (signed/temp URL) |
| `GET` | `/api/v1/jobs` | List all jobs (paginated, filterable by status) |
| `DELETE` | `/api/v1/jobs/{id}` | Delete job + associated files |
| `GET` | `/api/v1/health` | Health check (liveness/readiness) |

### Example: Create Job Request

```http
POST /api/v1/jobs HTTP/1.1
Content-Type: multipart/form-data; boundary=----X

------X
Content-Disposition: form-data; name="file"; filename="floorplan.pdf"
Content-Type: application/pdf

<binary pdf data>
------X
Content-Disposition: form-data; name="config"

{"mode": "3d", "dpi": 300, "floor_height_m": 3.0, "output_format": "dxf"}
------X--
```

### Example: SSE Progress Event

```
event: progress
data: {"job_id": "abc-123", "status": "processing", "progress": 42, "step": "Vectorization"}
```

---

## 6. Data Model (PostgreSQL)

```sql
-- Core job table
CREATE TABLE jobs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status       VARCHAR(20)  NOT NULL DEFAULT 'pending',  -- pending|queued|processing|completed|failed
    progress     SMALLINT     NOT NULL DEFAULT 0,          -- 0-100
    step         VARCHAR(50),                              -- current pipeline step name
    config       JSONB        NOT NULL DEFAULT '{}',       -- {mode, dpi, floor_height_m, ...}
    input_file   VARCHAR(500) NOT NULL,                    -- path/URL to uploaded PDF
    output_file  VARCHAR(500),                             -- path/URL to generated DWG/DXF
    page_count   SMALLINT,
    error_msg    TEXT,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX idx_jobs_status     ON jobs(status);
```

> Alembic manages schema migrations. Each schema change gets a versioned migration file.

---

## 7. Project Directory Layout

```
ai-file-converter/
├── frontend/                       # Next.js 14 (App Router)
│   ├── src/
│   │   ├── app/                    # Pages (App Router)
│   │   │   ├── layout.tsx         # Root layout + Toaster
│   │   │   ├── page.tsx           # Landing / upload page
│   │   │   ├── globals.css        # TailwindCSS globals
│   │   │   └── jobs/[id]/page.tsx # Job detail with live progress
│   │   ├── components/            # React components
│   │   │   ├── upload/            # DropZone, ConversionOptions
│   │   │   ├── job/               # ProgressTracker
│   │   │   └── shared/            # Button, Card
│   │   ├── lib/                    # API client, SSE helper
│   │   └── types/                  # TypeScript types (mirror backend schemas)
│   ├── public/                    # Static assets
│   ├── tailwind.config.ts
│   ├── next.config.js
│   ├── tsconfig.json
│   ├── package.json
│   └── Dockerfile
│
├── backend/                        # FastAPI + Celery
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── health.py      # GET /health
│   │   │       ├── jobs.py        # POST /jobs, GET /jobs/{id}, GET /jobs
│   │   │       └── jobs_stream.py # GET /jobs/{id}/stream (SSE)
│   │   ├── core/                   # Config (pydantic-settings), database
│   │   ├── models/                 # SQLAlchemy ORM (Job model)
│   │   ├── pipeline/               # PipelineContext, PipelineStep, orchestrator, progress publisher
│   │   ├── schemas/                # Pydantic request/response models
│   │   ├── storage/                # Storage adapter (LocalStorage, ABC)
│   │   └── tasks/                  # Celery app + placeholder pipeline
│   ├── tests/                      # pytest + fixtures (test_health.py)
│   ├── alembic/                    # DB migrations (0001_create_jobs_table)
│   ├── requirements.txt
│   ├── pyproject.toml              # ruff, mypy config
│   └── Dockerfile
│
├── scripts/                        # GitHub bootstrap & issue creation
├── docker-compose.yml              # Orchestrates all 5 services
├── .env.example                    # Environment variables template
├── .pre-commit-config.yaml         # Local lint/format/type-check hooks
├── .talismanrc                     # Pre-push hook config
├── README.md                       # ← you are here (architecture)
└── TODO.md                         # Execution tracker (GitHub Issues)
```

---

## 8. Design Patterns

### 8.1 Strategy — Pluggable Pipeline Steps
Each step implements a common interface so algorithms can be swapped without touching the orchestrator.

```python
class PipelineStep(ABC):
    name: str

    @abstractmethod
    def execute(self, context: PipelineContext) -> PipelineContext: ...
```

Concrete implementations: `PyMuPDFParser`, `OpenCVPreprocessor`, `YOLOSegmenter`, `ezdxfWriter`, etc. New approaches drop in without changing `Pipeline.run()`.

Implemented foundation:
- `backend/app/pipeline/context.py` defines the shared `PipelineContext` dataclass.
- `backend/app/pipeline/steps/base.py` defines the `PipelineStep` ABC.
- `backend/app/pipeline/orchestrator.py` provides `Pipeline.run()` for ordered step execution.
- `backend/app/pipeline/progress.py` provides Redis Pub/Sub progress publishing.

### 8.2 Observer / Pub-Sub — Progress Reporting
Workers publish progress events to **Redis Pub/Sub**. The FastAPI SSE endpoint subscribes and forwards events to the browser. This decouples the worker from the web layer and lets multiple workers report independently.

```python
# Worker
redis.publish(f"job:{job_id}", json.dumps({"progress": 42, "step": "vectorization"}))

# API SSE endpoint
async def stream(job_id: str):
    async with redis.pubsub() as pubsub:
        await pubsub.subscribe(f"job:{job_id}")
        async for message in pubsub.listen():
            yield f"data: {message['data']}\n\n"
```

### 8.3 Repository — Data Access
All DB operations go through `JobRepository` for testability and future storage swaps.

```python
class JobRepository(Protocol):
    async def create(self, job: Job) -> Job: ...
    async def get(self, job_id: UUID) -> Job | None: ...
    async def list(self, *, status: str | None = None, limit: int = 50) -> list[Job]: ...
    async def update_progress(self, job_id: UUID, progress: int, step: str) -> None: ...
```

### 8.4 Adapter — File Storage
`StorageBackend` abstract class with `LocalStorage` and `S3Storage` implementations. Selected via env variable — no application code changes to switch backends.

### 8.5 Functional Pipeline — Data Flow
The pipeline is a composed chain of steps. Each step is a pure function of the context.

```python
result = Pipeline([
    PyMuPDFParser(dpi=300),
    OpenCVPreprocessor(denoise_strength=7),
    YOLOSegmenter(model="floorplan-v1", device="cpu"),
    ContourVectorizer(simplify_tolerance=2.0),
    WallExtruder(default_height_m=3.0),     # only in 3D mode
    EzDxfWriter(format="dxf"),
]).run(context)
```

---

## 9. Key Trade-Offs

| Decision | Trade-Off | Mitigation |
|---|---|---|
| **Python over Node.js backend** | Better CV/ML libraries, but polyglot stack. | Clear REST contract; types mirrored in TS. |
| **DXF primary, DWG secondary** | Native DWG generation requires commercial ODA libs or unreliable open-source tools. | Offer ODA `FileConverter` as opt-in Docker step; most CAD software imports DXF perfectly. |
| **ML segmentation vs. traditional CV** | ML is more accurate on diverse drawings but needs GPU-friendly inference, model hosting, and periodic retraining. | Start with pre-trained model (e.g. trained on CubiCasa5K). Provide a "basic" OpenCV-only fallback for simple line drawings. |
| **Async (Celery) over synchronous** | Adds Redis + worker complexity. | Non-negotiable: conversions take 30s–5min and would timeout HTTP. Worker count scales horizontally. |
| **SSE over WebSocket** | SSE is unidirectional and slightly less flexible. | Sufficient for progress updates. WebSocket reserved for future live-edit features. |
| **ONNX Runtime over PyTorch** | Lighter weight and CPU-friendly for inference. | PyTorch reserved for training/fine-tuning in offline pipelines. |

---

## 10. Implementation Phases

### Phase 1 — Scaffolding & Upload Flow (MVP skeleton) ✅ Complete
- [x] Docker Compose with all 5 services (frontend, backend, worker, postgres, redis)
- [x] File upload endpoint (`POST /api/v1/jobs`) + Next.js drag-and-drop (DropZone)
- [x] Job creation in DB (PostgreSQL via SQLAlchemy + Alembic), PDF stored locally
- [x] Placeholder Celery pipeline that simulates conversion with progress updates
- [x] SSE progress streaming (`GET /api/v1/jobs/{id}/stream`) via Redis Pub/Sub
- [x] Frontend job detail page with live ProgressTracker
- [x] Conversion options UI (2D/3D, DPI, floor height, output format)

### Phase 2 — PDF Parsing & Preprocessing
- [x] Pluggable backend pipeline framework (`PipelineContext`, `PipelineStep`, `Pipeline.run()`)
- [x] Redis Pub/Sub progress publisher for pipeline steps
- PyMuPDF integration → extract pages as images
- OpenCV preprocessing pipeline
- Page preview in frontend

### Phase 3 — 2D Vectorization (core value)
- Integrate pre-trained floor plan segmentation model (e.g. fine-tuned on CubiCasa5K)
- Vectorize detected walls/doors/windows to DXF
- Downloadable DXF output

### Phase 4 — 3D Extrusion
- Extrude walls by configurable height
- Add floor slabs and door/window openings
- Export as 3D DXF (and optionally IFC)

### Phase 5 — Polish & DWG Export
- DWG conversion via `libredwg` or ODA `FileConverter`
- History page, job management, search/filter
- Robust error handling, retries with backoff
- File cleanup with TTL (e.g. 7 days)

---

## 11. Python Dependencies (Key Libraries)

```text
# backend/requirements.txt (implemented)
fastapi==0.115.*
uvicorn[standard]==0.34.*
celery[redis]==5.*
sqlalchemy[asyncio]==2.*
asyncpg==0.30.*
pydantic-settings==2.*
python-multipart==0.0.*  # file uploads
alembic==1.*              # migrations
redis==5.*               # Celery broker + Pub/Sub
sse-starlette==2.*       # SSE streaming
ruff==0.8.*              # linting
mypy==1.*                # type checking
pre-commit==4.*          # local Git quality gates
pytest==8.*              # testing
pytest-asyncio==0.24.*
httpx==0.28.*            # test client

# Planned for Phase 2+ (not yet installed)
# pymupdf                   # PDF parsing
# opencv-python-headless    # image preprocessing
# numpy
# ezdxf                     # DXF generation (reliable, open)
# libredwg (system-level)   # optional DWG support
# onnxruntime               # production inference
# torch + ultralytics       # training / fine-tuning
```

```jsonc
// frontend/package.json (key dependencies)
{
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "typescript": "^5.4.0",
    "tailwindcss": "^3.4.0",
    "react-dropzone": "^14.2.0",
    "sonner": "^1.4.0",
    "zod": "^3.23.0"
  }
}
```

---

## 12. Local Development (Quick Start)

The application is fully runnable via Docker Compose:

```bash
# 1. Clone & configure
cp .env.example .env

# 2. Boot all 5 services (frontend, backend, worker, postgres, redis)
docker compose up -d --build

# 3. Run DB migrations
docker compose exec backend alembic upgrade head

# 4. Open the app
open http://localhost:3000      # Frontend (Next.js)
open http://localhost:8000/api/v1/health  # Backend health check
```

### Services

| Service     | Port  | Description |
|-------------|-------|-------------|
| Frontend    | 3000  | Next.js 14 App Router |
| FastAPI     | 8000  | Backend API + SSE streaming |
| PostgreSQL  | 5432  | Job metadata database |
| Redis       | 6379  | Celery broker + Pub/Sub for SSE |
| Worker      | —     | Celery worker (shares backend image) |

### Development without Docker

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Linting & Tests

```bash
# Backend
cd backend
ruff check .          # linting
ruff format --check . # formatting check
mypy app/             # type checking
pytest                # tests

# Frontend
cd frontend
npm run lint          # ESLint
npm run format:check  # Prettier formatting check
npm run build         # production build
```

### Pre-commit hooks

Install the Git pre-commit hook after setting up the backend and frontend dependencies:

```bash
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
pre-commit install
```

Run the full hook suite manually with:

```bash
pre-commit run --all-files
```

The hook runs backend Ruff lint/format checks, backend mypy, frontend ESLint, and frontend Prettier checks before each commit.

---

## 13. Project & Issue Management (GitHub)

All implementation work is tracked as **GitHub Issues** on this repository. We use two equivalent mechanisms:

- **[GitHub CLI](https://cli.github.com/)** (`gh`) — terminal-native scripting & automation
- **GitHub MCP server** — for AI agents like Cline, Claude Desktop, and Cursor

No Linear, Jira, or other third-party trackers are required.

### Concept Mapping

| This document | GitHub |
|---|---|
| **Stage** (0–5) | **Milestone** (one per stage, with due date) |
| **Epic** (e.g. 1.1) | **Label** (`epic:p1-scaffold`, etc.) |
| **User Story** (US-001 …) | **Issue** with title prefix `[US-001]` |
| **Acceptance Criteria / Tasks** | **Markdown checkboxes** in the issue body |
| **Priority** (P0–P3) | **Label** `priority:p0` … `priority:p3` |
| **Area / Type** | **Labels** `area:backend`, `type:feature`, etc. |
| **Status** | **Project board column** (Backlog → Todo → In Progress → In Review → Done) |
| **Sprint / Cycle** | **GitHub Project iteration** or **Milestone due date** |

### Quick Start with the `gh` CLI

```bash
# 1. Install & authenticate
brew install gh
gh auth login

# 2. One-shot bootstrap: create labels + milestones
bash scripts/bootstrap-github.sh    # generated from TODO.md §A.3

# 3. Create one issue per user story (28 total)
bash scripts/create-issues.sh       # generated from TODO.md §A.4

# 4. Daily flow
gh issue list --assignee @me --state open
gh pr create --title "[US-001] Monorepo layout" --body "Closes #12"
```

### Using the GitHub MCP Server (from an AI agent)

When Cline or another MCP-enabled client has the GitHub MCP server connected, the same operations are available as tool calls:

| Action | MCP tool |
|---|---|
| Create issue | `mcp_github_create_issue({ title, body, labels, milestone })` |
| List my issues | `mcp_github_list_issues({ assignee: "me", state: "open" })` |
| Comment / progress | `mcp_github_add_issue_comment({ issue_number, body })` |
| Update state | `mcp_github_update_issue({ issue_number, labels, state })` |
| Create PR | `mcp_github_create_pull_request({ title, body, head, base })` |
| Search code | `mcp_github_search_code({ q: "repo:owner/name PipelineStep" })` |

### Branch & PR Auto-Linking

GitHub auto-links branches and PRs when the issue number appears in the branch name or PR title.

```bash
# Branch pattern
git checkout -b feat/12-monorepo-layout

# PR title pattern (auto-closes the issue on merge)
gh pr create --title "[US-001] Monorepo layout" --body "Closes #12"
```

### Detailed Reference

See [TODO.md §A](./TODO.md) for the full GitHub issue management playbook, including:
- Complete label / milestone bootstrap script
- Bulk issue creation from `TODO.md`
- Project board setup
- AI-agent MCP workflows

---

## 14. Open Questions & Future Considerations

- **Authentication** — Currently single-user. Add JWT-based auth + per-user job isolation when multi-tenancy is needed.
- **Model fine-tuning** — Plan a feedback loop where users can mark a conversion as "good/bad" to gather training data.
- **GPU support** — Optional `docker-compose.gpu.yml` for CUDA-enabled inference.
- **IFC export** — For full BIM interoperability, add an IFC writer alongside DXF/DWG.
- **Cloud-native deployment** — Replace Celery with AWS SQS + Lambda, or Kubernetes Jobs, for elastic scaling.

---

*Document version 0.3 — updated to reflect Phase 1 implementation and Phase 2 pipeline infrastructure.*
