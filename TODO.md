# TODO — AI File Converter Implementation Tracker

> Living document that decomposes the [README.md](./README.md) architecture into actionable work.
> Structure follows GitHub Issues–style tracking: **Stages → Epics (Milestones/Labels) → User Stories (Issues) → Tasks (sub-checklists)**.
> Each item includes priority, effort estimate, acceptance criteria, and dependencies.
> Issue management is driven by the **GitHub CLI (`gh`)** and/or the **GitHub MCP server** — no Linear dependency.

---

## Conventions

### Priority Levels
| Code | Meaning | Use when |
|---|---|---|
| **P0** | Critical / Blocker | Cannot ship without it |
| **P1** | High | Core MVP functionality |
| **P2** | Medium | Required for polished MVP |
| **P3** | Low | Nice-to-have / future |

### Effort Estimation (T-Shirt Sizes)
- **XS** — < 1 hour
- **S** — 1–4 hours
- **M** — 0.5–1 day
- **L** — 1–3 days
- **XL** — 3+ days (should be split)

### Status
`⬜ Backlog` · `🟦 Todo` · `🚧 In Progress` · `👀 In Review` · `✅ Done` · `❌ Blocked` · `⛔ Canceled`

### Labels
`area:frontend` · `area:backend` · `area:devops` · `area:ml` · `area:docs`
`type:bug` · `type:chore` · `type:spike` · `type:feature`
`epic:p1-scaffold` · `epic:p2-pdf` · `epic:p3-vectorize` · `epic:p4-3d` · `epic:p5-polish`

---

## Stage Overview

| # | Stage | Goal | Status | Stories | Tasks |
|---|---|---|---|---|---|
| 0 | **Bootstrap** | Repo, tooling, CI scaffold | 🚧 In Progress | 4 | 12 |
| 1 | **Phase 1 — MVP Skeleton** | Upload + queue + job tracking | 👀 In Review | 5 | 18 |
| 2 | **Phase 2 — PDF Parsing** | Extract & preview page images | ⬜ Backlog | 4 | 14 |
| 3 | **Phase 3 — 2D Vectorization** | PDF → DXF (core value) | ⬜ Backlog | 5 | 16 |
| 4 | **Phase 4 — 3D Extrusion** | Walls → 3D model | ⬜ Backlog | 4 | 12 |
| 5 | **Phase 5 — Polish & DWG** | Production-ready with DWG export | ⬜ Backlog | 6 | 20 |

**Total: 28 user stories · 92 actionable tasks**

---

## Progress Log

| Date | Milestone | PR | Stories completed | Notes |
|---|---|---|---|---|
| 2025-07-22 | Stage 0 — US-001 | [#30](https://github.com/Josh-Uvi/DrawLift/pull/30) (merged) | US-001 | Monorepo layout, `.gitignore`, `LICENSE`, `README.md` |
| 2025-07-23 | Stage 0 + Stage 1 — Phase 1 | [#31](https://github.com/Josh-Uvi/DrawLift/pull/31) (open) | US-002 → US-011 | Full Phase 1 implementation: FastAPI backend, Next.js 14 frontend, Docker Compose, CI, Celery, SSE streaming. US-003 partially complete (pre-commit hook pending). |

---

# Stage 0 — Bootstrap & Tooling

> **Goal:** Establish the repo skeleton, monorepo structure, dev tooling, and CI so all subsequent work can plug in cleanly.

## Epic 0.1 — Repository Structure

### US-001 · As a developer, I want a monorepo layout with `frontend/` and `backend/` folders
- **Priority:** P0 · **Effort:** S · **Status:** ✅ Done · **Labels:** `area:devops`, `type:chore`
- **PR:** [#30](https://github.com/Josh-Uvi/DrawLift/pull/30) (merged to `main` at `5ae452a`)
- **Acceptance Criteria:**
  - [x] `frontend/` and `backend/` directories created
  - [x] Root `.gitignore` covers Node, Python, IDE, OS files
  - [x] Root `README.md` links to `TODO.md` and architecture doc
  - [x] `LICENSE` file present
- **Tasks:**
  - [x] T-001 — Create `frontend/` and `backend/` directories
  - [x] T-002 — Write root `.gitignore`
  - [x] T-003 — Add `LICENSE` (MIT recommended for POC)
  - [x] T-004 — Update README to reference TODO.md

## Epic 0.2 — Docker Compose Foundations

### US-002 · As a developer, I want `docker compose up` to start all services
- **Priority:** P0 · **Effort:** M · **Status:** 👀 In Review · **Labels:** `area:devops`, `type:feature`
- **PR:** [#31](https://github.com/Josh-Uvi/DrawLift/pull/31)
- **Acceptance Criteria:**
  - [x] `docker-compose.yml` defines: `frontend`, `backend`, `worker`, `postgres`, `redis`
  - [x] All services start without errors
  - [x] Health check endpoint on backend responds 200
  - [x] Frontend reachable at `http://localhost:3000`
- **Tasks:**
  - [x] T-005 — Write `docker-compose.yml` with 5 services
  - [x] T-006 — Write `.env.example` with all required variables
  - [x] T-007 — Write `backend/Dockerfile` (Python 3.11-slim)
  - [x] T-008 — Write `frontend/Dockerfile` (Node 20-alpine, multi-stage)
  - [x] T-009 — Wire service dependencies (backend → postgres, redis; worker → backend image)

## Epic 0.3 — Code Quality Tooling

### US-003 · As a developer, I want linting and formatting pre-configured
- **Priority:** P1 · **Effort:** S · **Status:** 🚧 In Progress · **Labels:** `area:devops`, `type:chore`
- **PR:** [#31](https://github.com/Josh-Uvi/DrawLift/pull/31) (linting configured; pre-commit hook pending)
- **Acceptance Criteria:**
  - [x] Backend: `ruff` (lint + format) and `mypy` configured
  - [x] Frontend: `eslint` + `prettier` configured
  - [ ] `pre-commit` hook runs both linters
- **Tasks:**
  - [x] T-010 — Configure `ruff.toml` and `pyproject.toml` for backend
  - [x] T-011 — Configure `eslint.config.js` and `.prettierrc` for frontend

### US-004 · As a developer, I want a basic CI pipeline on GitHub Actions
- **Priority:** P2 · **Effort:** S · **Status:** 👀 In Review · **Labels:** `area:devops`, `type:feature`
- **PR:** [#31](https://github.com/Josh-Uvi/DrawLift/pull/31)
- **Acceptance Criteria:**
  - [x] CI runs on PR + push to `main`
  - [x] Lints backend and frontend
  - [x] Builds Docker images to validate Dockerfile syntax
- **Tasks:**
  - [x] T-012 — Write `.github/workflows/ci.yml`

---

# Stage 1 — Phase 1: MVP Skeleton (Upload & Job Tracking)

> **Goal:** User can upload a PDF, see it queued, and observe status updates. No real conversion yet — just a placeholder pipeline that "succeeds".

## Epic 1.1 — Backend Foundation

### US-005 · As a backend dev, I want a FastAPI skeleton with health checks and config
- **Priority:** P0 · **Effort:** M · **Status:** 👀 In Review · **Labels:** `area:backend`, `epic:p1-scaffold`
- **PR:** [#31](https://github.com/Josh-Uvi/DrawLift/pull/31)
- **Acceptance Criteria:**
  - [x] `GET /api/v1/health` returns `{"status": "ok"}`
  - [x] Pydantic settings load from `.env`
  - [x] CORS configured to allow frontend origin
  - [x] OpenAPI docs at `/docs`
- **Tasks:**
  - [x] T-013 — Create `backend/app/main.py` with FastAPI app
  - [x] T-014 — Create `backend/app/core/config.py` with pydantic-settings
  - [x] T-015 — Add CORS middleware
  - [x] T-016 — Create `backend/app/api/v1/health.py`

### US-006 · As a backend dev, I want PostgreSQL connected via SQLAlchemy (async)
- **Priority:** P0 · **Effort:** M · **Status:** 👀 In Review · **Labels:** `area:backend`, `epic:p1-scaffold`
- **PR:** [#31](https://github.com/Josh-Uvi/DrawLift/pull/31)
- **Acceptance Criteria:**
  - [x] `Job` model matches the schema in README §6
  - [x] `alembic upgrade head` creates `jobs` table
  - [x] Async session dependency in FastAPI
- **Tasks:**
  - [x] T-017 — Create `backend/app/models/job.py` SQLAlchemy model
  - [x] T-018 — Create `backend/app/core/database.py` async engine + session
  - [x] T-019 — Initialise Alembic, write first migration for `jobs` table
  - [x] T-020 — Create `JobRepository` with CRUD methods

### US-007 · As a backend dev, I want Celery wired to Redis
- **Priority:** P0 · **Effort:** S · **Status:** 👀 In Review · **Labels:** `area:backend`, `epic:p1-scaffold`
- **PR:** [#31](https://github.com/Josh-Uvi/DrawLift/pull/31)
- **Acceptance Criteria:**
  - [x] `celery -A app.tasks.celery_app worker` starts without errors
  - [x] A dummy task can be enqueued and executed
  - [x] Result backend persists in Redis
- **Tasks:**
  - [x] T-021 — Create `backend/app/tasks/celery_app.py` with Celery config
  - [x] T-022 — Create `backend/app/tasks/placeholder.py` dummy task

## Epic 1.2 — File Upload API

### US-008 · As a user, I want to upload a PDF and receive a `job_id`
- **Priority:** P0 · **Effort:** M · **Status:** 👀 In Review · **Labels:** `area:backend`, `epic:p1-scaffold`
- **PR:** [#31](https://github.com/Josh-Uvi/DrawLift/pull/31)
- **Acceptance Criteria:**
  - [x] `POST /api/v1/jobs` accepts `multipart/form-data` with `file` + `config`
  - [x] Only `.pdf` files accepted (validated by MIME + extension)
  - [x] File saved to local `storage/` directory (or S3 in prod)
  - [x] Job row created in DB with `status=pending`
  - [x] Celery task enqueued
  - [x] Response: `201 { "job_id": "uuid" }`
- **Tasks:**
  - [x] T-023 — Create `backend/app/schemas/job.py` Pydantic models
  - [x] T-024 — Create `backend/app/storage/local.py` (with `StorageBackend` interface)
  - [x] T-025 — Create `backend/app/api/v1/jobs.py` with `POST /jobs` handler
  - [x] T-026 — Add `GET /jobs/{id}` and `GET /jobs` endpoints
  - [x] T-027 — Wire placeholder Celery task to update job status

## Epic 1.3 — Frontend Foundation

### US-009 · As a user, I want a clean landing page with a file drop zone
- **Priority:** P0 · **Effort:** M · **Status:** 👀 In Review · **Labels:** `area:frontend`, `epic:p1-scaffold`
- **PR:** [#31](https://github.com/Josh-Uvi/DrawLift/pull/31)
- **Acceptance Criteria:**
  - [x] Next.js 14 App Router project initialised in `frontend/`
  - [x] Tailwind configured
  - [x] Landing page renders `<DropZone />` component
  - [x] Drag-and-drop and click-to-browse both work
  - [x] Only `.pdf` accepted with friendly error message
- **Tasks:**
  - [x] T-028 — Initialise Next.js 14 with TypeScript + Tailwind
  - [x] T-029 — Install `react-dropzone` and `sonner`
  - [x] T-030 — Create `components/upload/DropZone.tsx`
  - [x] T-031 — Create `components/shared/Button.tsx` and `Card.tsx`
  - [x] T-032 — Create `app/page.tsx` landing page

### US-010 · As a user, I want to see conversion options before submitting
- **Priority:** P1 · **Effort:** S · **Status:** 👀 In Review · **Labels:** `area:frontend`, `epic:p1-scaffold`
- **PR:** [#31](https://github.com/Josh-Uvi/DrawLift/pull/31)
- **Acceptance Criteria:**
  - [x] 2D/3D mode toggle
  - [x] DPI slider (150/300/600)
  - [x] Floor height input (only when 3D)
  - [x] Submit button disabled until file chosen
- **Tasks:**
  - [x] T-033 — Create `components/upload/ConversionOptions.tsx`
  - [x] T-034 — Wire options to dropzone state via React Hook Form or local state

### US-011 · As a user, I want to see live progress after submitting
- **Priority:** P0 · **Effort:** M · **Status:** 👀 In Review · **Labels:** `area:frontend`, `epic:p1-scaffold`
- **PR:** [#31](https://github.com/Josh-Uvi/DrawLift/pull/31)
- **Acceptance Criteria:**
  - [x] On submit, redirected to `/jobs/{id}`
  - [x] Progress bar updates from SSE stream
  - [x] Status badges for `pending` / `processing` / `completed` / `failed`
- **Tasks:**
  - [x] T-035 — Create `app/jobs/[id]/page.tsx`
  - [x] T-036 — Create `lib/sse.ts` EventSource wrapper
  - [x] T-037 — Create `components/job/ProgressTracker.tsx`
  - [x] T-038 — Implement `GET /api/v1/jobs/{id}/stream` SSE endpoint on backend

---

# Stage 2 — Phase 2: PDF Parsing & Preprocessing

> **Goal:** Extract page images from the uploaded PDF, apply basic image cleanup, and show previews in the UI.

## Epic 2.1 — Pipeline Infrastructure

### US-012 · As a backend dev, I want a pluggable pipeline framework
- **Priority:** P0 · **Effort:** M · **Status:** ⬜ Backlog · **Labels:** `area:backend`, `epic:p2-pdf`
- **Acceptance Criteria:**
  - [ ] `PipelineStep` ABC defined
  - [ ] `PipelineContext` dataclass defined
  - [ ] `Pipeline.run()` executes steps in order
  - [ ] Each step can publish progress to Redis
- **Tasks:**
  - [ ] T-039 — Create `backend/app/pipeline/steps/base.py` with `PipelineStep` ABC
  - [ ] T-040 — Create `backend/app/pipeline/context.py`
  - [ ] T-041 — Create `backend/app/pipeline/__init__.py` orchestrator
  - [ ] T-042 — Add progress publishing helper (Redis Pub/Sub)

### US-013 · As a backend dev, I want PyMuPDF-based PDF page extraction
- **Priority:** P0 · **Effort:** M · **Status:** ⬜ Backlog · **Labels:** `area:backend`, `epic:p2-pdf`
- **Acceptance Criteria:**
  - [ ] Step 1: extracts each page as a PNG at configurable DPI
  - [ ] Returns list of page image paths in `PipelineContext.page_images`
  - [ ] Reports `progress = 20%`
- **Tasks:**
  - [ ] T-043 — Add `pymupdf` to requirements
  - [ ] T-044 — Implement `PdfParserStep` in `backend/app/pipeline/steps/pdf_parser.py`

### US-014 · As a backend dev, I want an OpenCV preprocessing step
- **Priority:** P1 · **Effort:** M · **Status:** ⬜ Backlog · **Labels:** `area:backend`, `epic:p2-pdf`
- **Acceptance Criteria:**
  - [ ] Converts to grayscale
  - [ ] Applies Gaussian blur + adaptive threshold
  - [ ] Deskew correction
  - [ ] Reports `progress = 35%`
- **Tasks:**
  - [ ] T-045 — Add `opencv-python-headless` and `numpy`
  - [ ] T-046 — Implement `OpenCVPreprocessor` in `backend/app/pipeline/steps/preprocessor.py`
  - [ ] T-047 — Unit test on a sample architectural drawing

## Epic 2.2 — Frontend Preview

### US-015 · As a user, I want to see extracted page thumbnails on the job page
- **Priority:** P1 · **Effort:** S · **Status:** ⬜ Backlog · **Labels:** `area:frontend`, `epic:p2-pdf`
- **Acceptance Criteria:**
  - [ ] `/jobs/{id}/pages/{n}` endpoint serves extracted page images
  - [ ] Job detail page shows a horizontal strip of page thumbnails
  - [ ] Click thumbnail to enlarge in modal
- **Tasks:**
  - [ ] T-048 — Add `GET /api/v1/jobs/{id}/pages/{n}` endpoint
  - [ ] T-049 — Create `components/job/PageViewer.tsx`
  - [ ] T-050 — Integrate `PageViewer` into `app/jobs/[id]/page.tsx`
  - [ ] T-051 — Add image modal component

---

# Stage 3 — Phase 3: 2D Vectorization (Core Value)

> **Goal:** Convert the cleaned raster page images into parametric CAD primitives and export to DXF.

## Epic 3.1 — Semantic Segmentation

### US-016 · As a backend dev, I want to integrate an ML segmentation model
- **Priority:** P0 · **Effort:** L · **Status:** ⬜ Backlog · **Labels:** `area:ml`, `area:backend`, `epic:p3-vectorize`
- **Acceptance Criteria:**
  - [ ] Model loads once at worker startup (not per request)
  - [ ] Inference runs on CPU via ONNX Runtime
  - [ ] Returns per-pixel masks for: walls, doors, windows, rooms, text
  - [ ] Reports `progress = 60%`
- **Tasks:**
  - [ ] T-052 — Spike: Evaluate pre-trained floor plan models (CubiCasa5K-based)
  - [ ] T-053 — Add `onnxruntime` to requirements
  - [ ] T-054 — Implement `SegmenterStep` in `backend/app/pipeline/steps/segmenter.py`
  - [ ] T-055 — Download/cache ONNX model weights in `models/` volume
  - [ ] T-056 — Unit test inference on sample input

### US-017 · As a backend dev, I want a non-ML fallback for simple line drawings
- **Priority:** P2 · **Effort:** L · **Status:** ⬜ Backlog · **Labels:** `area:backend`, `epic:p3-vectorize`
- **Acceptance Criteria:**
  - [ ] `ClassicCVSegmenter` using threshold + Hough line detection
  - [ ] User-selectable via job config (`segmenter: "ml" | "classic"`)
  - [ ] Significantly faster than ML path
- **Tasks:**
  - [ ] T-057 — Implement `ClassicCVSegmenter`
  - [ ] T-058 — Add config flag in `PipelineContext`

## Epic 3.2 — Vectorization

### US-018 · As a backend dev, I want to convert masks into CAD primitives
- **Priority:** P0 · **Effort:** L · **Status:** ⬜ Backlog · **Labels:** `area:backend`, `epic:p3-vectorize`
- **Acceptance Criteria:**
  - [ ] Wall segments become `(start, end, thickness)` primitives
  - [ ] Doors and windows become parametric blocks
  - [ ] Polygon simplification reduces noise
  - [ ] Reports `progress = 80%`
- **Tasks:**
  - [ ] T-059 — Define `Primitive` dataclasses in `backend/app/pipeline/primitives.py`
  - [ ] T-060 — Implement `VectorizerStep` in `backend/app/pipeline/steps/vectorizer.py`
  - [ ] T-061 — Implement wall thinning + Douglas-Peucker simplification
  - [ ] T-062 — Unit test with synthetic mask input

## Epic 3.3 — DXF Writer

### US-019 · As a backend dev, I want to write primitives to DXF using `ezdxf`
- **Priority:** P0 · **Effort:** M · **Status:** ⬜ Backlog · **Labels:** `area:backend`, `epic:p3-vectorize`
- **Acceptance Criteria:**
  - [ ] DXF file is generated and stored in output path
  - [ ] Layers: `WALLS`, `DOORS`, `WINDOWS`, `ROOMS`, `TEXT`
  - [ ] Output DXF opens in AutoCAD / LibreCAD without errors
  - [ ] Reports `progress = 95%`
- **Tasks:**
  - [ ] T-063 — Add `ezdxf` to requirements
  - [ ] T-064 — Implement `DxfWriterStep` in `backend/app/pipeline/steps/dwg_writer.py`
  - [ ] T-065 — Test DXF output with LibreCAD or `ezdxf` round-trip

### US-020 · As a user, I want to download the generated DXF file
- **Priority:** P0 · **Effort:** S · **Status:** ⬜ Backlog · **Labels:** `area:frontend`, `epic:p3-vectorize`
- **Acceptance Criteria:**
  - [ ] "Download" button appears when job status is `completed`
  - [ ] `GET /api/v1/jobs/{id}/download` returns DXF with correct Content-Disposition
- **Tasks:**
  - [ ] T-066 — Add `GET /api/v1/jobs/{id}/download` endpoint
  - [ ] T-067 — Create `components/job/DownloadButton.tsx`

---

# Stage 4 — Phase 4: 3D Extrusion

> **Goal:** Given a 2D vectorized floor plan, extrude walls into 3D and add slabs.

## Epic 4.1 — Wall Extrusion

### US-021 · As a backend dev, I want to extrude wall segments into 3D volumes
- **Priority:** P0 · **Effort:** M · **Status:** ⬜ Backlog · **Labels:** `area:backend`, `epic:p4-3d`
- **Acceptance Criteria:**
  - [ ] Each wall becomes a rectangular prism with floor-height as Z-dimension
  - [ ] Walls respect their original `(start, end, thickness)` geometry
  - [ ] Configurable floor height (default 3.0m)
  - [ ] Reports `progress = 85%`
- **Tasks:**
  - [ ] T-068 — Implement `WallExtruderStep` in `backend/app/pipeline/steps/extruder.py`
  - [ ] T-069 — Update `Primitive` dataclass to support 3D (3D point + extrusion)
  - [ ] T-070 — Add 3D primitives to DXF writer (use POLYLINE 3D / 3DFACE)

### US-022 · As a backend dev, I want to add floor and ceiling slabs
- **Priority:** P1 · **Effort:** M · **Status:** ⬜ Backlog · **Labels:** `area:backend`, `epic:p4-3d`
- **Acceptance Criteria:**
  - [ ] Detect room polygons from segmentation
  - [ ] Add a slab at z=0 covering the union of rooms
  - [ ] Optional ceiling at z=floor_height
- **Tasks:**
  - [ ] T-071 — Implement `SlabGenerator` helper in `primitives.py`
  - [ ] T-072 — Hook slab generation into `WallExtruderStep`
  - [ ] T-073 — Add slab thickness config (default 0.2m)

## Epic 4.2 — 3D Preview & Export

### US-023 · As a user, I want to see a 3D preview of the generated model in the browser
- **Priority:** P2 · **Effort:** M · **Status:** ⬜ Backlog · **Labels:** `area:frontend`, `epic:p4-3d`
- **Acceptance Criteria:**
  - [ ] Job detail page renders a 3D scene when job mode is `3d`
  - [ ] Orbit controls (zoom, pan, rotate)
  - [ ] Toggle between wireframe and solid shading
- **Tasks:**
  - [ ] T-074 — Add `three` and `@react-three/fiber` to frontend deps
  - [ ] T-075 — Create `components/job/Model3DPreview.tsx`
  - [ ] T-076 — Parse DXF into Three.js geometry in the browser
  - [ ] T-077 — Add view-mode toggle in `ConversionOptions`

### US-024 · As a user, I want to download the 3D model in a standard format
- **Priority:** P2 · **Effort:** M · **Status:** ⬜ Backlog · **Labels:** `area:backend`, `epic:p4-3d`
- **Acceptance Criteria:**
  - [ ] In addition to DXF, export to GLB (binary glTF)
  - [ ] GLB is a single self-contained file
  - [ ] Opens in any 3D viewer (Blender, online viewers)
- **Tasks:**
  - [ ] T-078 — Add `pygltflib` or `trimesh` to requirements
  - [ ] T-079 — Implement `GlbWriterStep` in `backend/app/pipeline/steps/glb_writer.py`
  - [ ] T-080 — Update download endpoint to return `output.glb` when format=glb

---

# Stage 5 — Phase 5: Polish, DWG Export & Production Readiness

> **Goal:** Add DWG export, robust error handling, history UI, and prepare for production.

## Epic 5.1 — DWG Export

### US-025 · As a user, I want to download a true DWG file (not just DXF)
- **Priority:** P1 · **Effort:** L · **Status:** ⬜ Backlog · **Labels:** `area:backend`, `epic:p5-polish`
- **Acceptance Criteria:**
  - [ ] DWG file generated alongside DXF
  - [ ] Uses `libredwg` or ODA `FileConverter` (Docker sidecar)
  - [ ] User-selectable output format (DXF / DWG / both)
  - [ ] Output opens in AutoCAD without conversion errors
- **Tasks:**
  - [ ] T-081 — Spike: Choose between libredwg vs ODA FileConverter
  - [ ] T-082 — Add DWG conversion service (Docker service in `docker-compose.yml`)
  - [ ] T-083 — Implement `DwgConverter` post-processor
  - [ ] T-084 — Update job config to accept `output_format: "dxf" | "dwg" | "both"`

## Epic 5.2 — History & Job Management

### US-026 · As a user, I want to see my past conversions
- **Priority:** P1 · **Effort:** M · **Status:** ⬜ Backlog · **Labels:** `area:frontend`, `epic:p5-polish`
- **Acceptance Criteria:**
  - [ ] `/history` page lists all past jobs
  - [ ] Sortable by date, filterable by status
  - [ ] Click to re-open job detail page
  - [ ] Delete button with confirmation
- **Tasks:**
  - [ ] T-085 — Create `app/history/page.tsx`
  - [ ] T-086 — Implement `GET /api/v1/jobs?status=...&page=...` pagination
  - [ ] T-087 — Create `components/history/JobTable.tsx`
  - [ ] T-088 — Implement `DELETE /api/v1/jobs/{id}` frontend action

## Epic 5.3 — Error Handling & Resilience

### US-027 · As a backend dev, I want robust error handling and retries
- **Priority:** P1 · **Effort:** M · **Status:** ⬜ Backlog · **Labels:** `area:backend`, `epic:p5-polish`
- **Acceptance Criteria:**
  - [ ] Failed jobs store `error_msg` and a stack trace
  - [ ] Celery task retries with exponential backoff (3 attempts)
  - [ ] User sees actionable error message in UI
  - [ ] "Retry" button re-enqueues the job with same config
- **Tasks:**
  - [ ] T-089 — Add retry decorator to Celery tasks
  - [ ] T-090 — Implement global exception handler in FastAPI
  - [ ] T-091 — Add error toast in `DownloadButton` and `ProgressTracker`

## Epic 5.4 — File Lifecycle & Storage

### US-028 · As an operator, I want uploaded and output files auto-cleaned after 7 days
- **Priority:** P2 · **Effort:** S · **Status:** ⬜ Backlog · **Labels:** `area:backend`, `epic:p5-polish`
- **Acceptance Criteria:**
  - [ ] Celery beat task runs daily
  - [ ] Deletes files older than 7 days
  - [ ] Marks corresponding jobs as `archived`
  - [ ] Logs the cleanup activity
- **Tasks:**
  - [ ] T-092 — Create `backend/app/tasks/cleanup.py` beat schedule
  - [ ] T-093 — Add `archived` status enum value
  - [ ] T-094 — Wire beat into `docker-compose.yml`

---

# Appendix A — GitHub Issue Management (via `gh` CLI & GitHub MCP)

All implementation work is tracked as **GitHub Issues** on the project repo. Two equivalent ways to manage them: the **GitHub CLI (`gh`)** from the terminal, or the **GitHub MCP server** from inside an AI agent (e.g. Cline, Claude Desktop, Cursor).

> **Status (this repo):** the project board, 28 user-story issues, 6 milestones, all labels, and the auto-sync workflows are already in place. See the **AI File Converter** project: https://github.com/users/Josh-Uvi/projects/1
>
> The exact one-shot scripts used to bootstrap everything from scratch live in `scripts/` (`bootstrap-github.sh`, `create-issues.py` + `stories.json`, `add-to-project.py`).

## A.0 Live state of this repo

| Resource | Where |
|---|---|
| Project board | https://github.com/users/Josh-Uvi/projects/1 (Status: `Todo` / `In Progress` / `Done`) |
| Milestones (one per stage) | `Stage 0: Bootstrap` -> `Stage 5: Polish & DWG` (6 total) |
| User-story issues | `#1` ... `#28` (one per `US-###` defined below) |
| Parent tracking issue | `#29` - "AI File Converter - PDF to DWG (project root)" |
| Auto-sync workflow | `.github/workflows/project-sync.yml` |
| CI workflow | `.github/workflows/ci.yml` |

## A.6 Automation: workflows on push and PR

Two GitHub Actions workflows drive the board. Both run automatically on every push to `main` and on every pull request.

**`ci.yml`** - Lint + Docker build validation (3 parallel jobs: `backend`, `frontend`, `docker`).

**`project-sync.yml`** - The key board automation. It listens for `issues`, `pull_request`, and `push` events and, via the GraphQL API, moves the linked card to the correct Status column:

| Event | Card moves to |
|---|---|
| Issue `opened` / `reopened` | `Todo` |
| Pull request `opened` / `synchronize` | `In Progress` |
| Issue `closed` | `Done` |
| Pull request `closed` (merged or not) | `Done` |
| Push to `main` whose commit message contains `Closes #N` / `Fixes #N` | `Done` (and the issue is auto-closed) |

The default `GITHUB_TOKEN` is sufficient. If your org requires finer-grained permissions, add a `PROJECT_TOKEN` secret (PAT with `project` scope) and the workflow will prefer it.

## A.10 Daily developer flow (with the automation in place)

```bash
# 1. Pick an issue and create a feature branch
gh issue list --label "epic:p1-scaffold" --state open
git checkout -b feat/9-landing-dropzone      # 9 = US-009 issue number

# 2. Implement, commit with the auto-close keyword
git commit -m "feat(frontend): landing dropzone

Closes #9"

# 3. Push and open a PR (project-sync.yml moves #9 to In Progress)
git push origin feat/9-landing-dropzone
gh pr create --base main --title "[US-009] Landing dropzone" --body "Closes #9"

# 4. Merge the PR (project-sync.yml moves #9 to Done and closes it)
gh pr merge --squash
```

No manual card dragging required.

## A.1 One-Time Setup

```bash
# 1. Install GitHub CLI (macOS)
brew install gh

# 2. Authenticate
gh auth login

# 3. Verify access to the project repo
gh repo view
```

## A.2 Mapping our Hierarchy → GitHub Concepts

| Our concept | GitHub equivalent |
|---|---|
| Stage (0–5) | **Milestone** |
| Epic (e.g. 0.1, 1.1) | **Label** (`epic:p1-scaffold`, etc.) |
| User Story (US-001 …) | **Issue** with title prefix `[US-001]` |
| Acceptance Criteria / Tasks | **Markdown checkboxes inside the issue body** |
| Priority (P0–P3) | **Label** `priority:p0` … `priority:p3` |
| Area / Type | **Labels** `area:backend`, `type:feature`, etc. |
| Status | **Project board column** or **Issue state** (open/closed) |
| Cycle / Sprint | **Milestone due date** or **GitHub Project iteration** |

## A.3 Bootstrap the Repo (Labels, Milestones, First Issues)

```bash
# --- Create labels (one shot) ---
for label in \
  "area:frontend" "area:backend" "area:devops" "area:ml" "area:docs" \
  "type:bug" "type:chore" "type:spike" "type:feature" \
  "epic:p1-scaffold" "epic:p2-pdf" "epic:p3-vectorize" "epic:p4-3d" "epic:p5-polish" \
  "priority:p0" "priority:p1" "priority:p2" "priority:p3" \
  "status:blocked" "status:in-review"; do
    gh label create "$label" --color "0E8A16" --description "Auto-generated" 2>/dev/null || true
done

# --- Create milestones (one per Stage) ---
for stage in "Stage 0: Bootstrap" "Stage 1: MVP Skeleton" "Stage 2: PDF Parsing" \
             "Stage 3: 2D Vectorization" "Stage 4: 3D Extrusion" "Stage 5: Polish & DWG"; do
    gh milestone create "$stage" --description "From TODO.md"
done

# --- Create the parent tracking issue (one per project) ---
gh issue create \
  --title "🎯 AI File Converter — PDF to DWG (project root)" \
  --body "Tracks the full build-out defined in README.md and TODO.md. See **Milestones** for stage-level breakdown." \
  --label "area:docs,type:feature"
```

## A.4 Create an Issue per User Story

The body of each issue should mirror the user story from `TODO.md`. Use a small bash loop or a script (`scripts/create-issues.sh`) to generate them in bulk.

```bash
gh issue create \
  --title "[US-001] Monorepo layout with frontend/ and backend/" \
  --milestone "Stage 0: Bootstrap" \
  --label "area:devops,type:chore,epic:p1-scaffold,priority:p0" \
  --body "$(cat <<'EOF'
## Context
Bootstrap the repository so that all subsequent stages can be developed in isolation.

## Acceptance Criteria
- [ ] `frontend/` and `backend/` directories created
- [ ] Root `.gitignore` covers Node, Python, IDE, OS files
- [ ] Root `README.md` links to `TODO.md` and architecture doc
- [ ] `LICENSE` file present

## Tasks
- [ ] T-001 — Create `frontend/` and `backend/` directories
- [ ] T-002 — Write root `.gitignore`
- [ ] T-003 — Add `LICENSE` (MIT recommended for POC)
- [ ] T-004 — Update README to reference TODO.md

## Definition of Done
- [ ] All acceptance criteria checked
- [ ] Lint passes
- [ ] PR merged to `main` (e.g. `Closes #1`)
EOF
)"
```

### Bulk-create from `TODO.md`

```bash
# Extract US-### titles from TODO.md and create an issue per story
grep -E '^### US-[0-9]+' TODO.md | sed -E 's/^### (US-[0-9]+) · (.*)$/[\1] \2/' \
  | while read -r line; do
      gh issue create --title "$line" --label "area:backend,epic:p1-scaffold"
    done
```

## A.5 Working with Issues (Daily Flow)

```bash
# List your open issues
gh issue list --assignee @me --state open

# View a specific issue
gh issue view 12

# Add a comment / progress update
gh issue comment 12 --body "Blocked on T-008. Pinging @teammate."

# Close an issue (with auto-close via PR keywords)
gh pr create --title "[US-001] Monorepo layout" --body "Closes #12" --base main
```

## A.6 Project Board (GitHub Projects v2)

```bash
# Create a project (web) then link issues to it
gh project create --title "AI File Converter" --owner <org-or-user>

# Add an issue to a project (item id from web URL)
gh project item-add <project-number> --owner <owner> --url <issue-url>
```

Typical columns: **Backlog → Todo → In Progress → In Review → Done**.

## A.7 Branch ↔ Issue Auto-Linking

GitHub auto-links branches & PRs when the branch name or PR title contains the issue number.

```bash
# Branch name pattern: <type>/<issue-number>-<short-desc>
git checkout -b feat/12-monorepo-layout

# PR title pattern: closes the issue
gh pr create --title "[US-001] Monorepo layout" --body "Closes #12"
```

## A.8 Using the GitHub MCP Server (for AI agents)

When Cline, Claude Desktop, or another MCP-compatible client has the **GitHub MCP server** enabled, the same workflow runs from the chat:

| Action | MCP tool call (pseudocode) |
|---|---|
| Create issue | `mcp_github_create_issue({ title, body, labels, milestone })` |
| List my issues | `mcp_github_list_issues({ assignee: "me", state: "open" })` |
| Comment on issue | `mcp_github_add_issue_comment({ issue_number, body })` |
| Update labels | `mcp_github_update_issue({ issue_number, labels: [...] })` |
| Create PR | `mcp_github_create_pull_request({ title, body, head, base })` |
| Search code | `mcp_github_search_code({ q: "repo:owner/name PipelineStep" })` |

The GitHub MCP server mirrors the `gh` CLI surface, so the bulk-creation script in §A.4 can be reproduced in a single agent prompt.

## A.9 Suggested Milestone Plan

| Milestone | Stories | Goal |
|---|---|---|
| **Stage 0: Bootstrap** | US-001 → US-004 | Repo, tooling, CI scaffold |
| **Stage 1: MVP Skeleton** | US-005 → US-011 | Upload + queue + job tracking |
| **Stage 2: PDF Parsing** | US-012 → US-015 | Extract & preview page images |
| **Stage 3: 2D Vectorization** | US-016 → US-020 | PDF → DXF (core value) |
| **Stage 4: 3D Extrusion** | US-021 → US-024 | Walls → 3D model |
| **Stage 5: Polish & DWG** | US-025 → US-028 | Production-ready with DWG export |

---

# Appendix B — Definition of Done

A user story is considered **Done** when:

- [ ] All acceptance criteria checkboxes are ticked
- [ ] All linked tasks (T-XXX) are completed
- [ ] Code passes linting (`ruff check` / `eslint`)
- [ ] Unit tests exist and pass (`pytest` / `vitest`)
- [ ] Feature is manually verified in `docker compose up` environment
- [ ] PR is merged to `main` with the GitHub issue number referenced (e.g. `Closes #12`)
- [ ] `CHANGELOG.md` updated (if user-facing change)
- [ ] Issue moved to **Done** column on the GitHub Project board

---

# Appendix C — Dependency Graph (Stage → Story)

```
Stage 0 (Bootstrap)
  └── US-001 ── US-002 ── US-003 ── US-004
                    │
Stage 1 (MVP)       ▼
  └── US-005 ── US-006 ── US-007 ── US-008 ── US-009 ── US-010 ── US-011
                                                          │
Stage 2 (PDF)                                              ▼
  └── US-012 ── US-013 ── US-014 ── US-015
                    │
Stage 3 (Vectorize)  ▼
  └── US-016 ── US-017 ── US-018 ── US-019 ── US-020
                                               │
Stage 4 (3D)                                    ▼
  └── US-021 ── US-022 ── US-023 ── US-024
                                       │
Stage 5 (Polish)                      ▼
  └── US-025 ── US-026 ── US-027 ── US-028
```

---

*Document version 0.2 — updated 2025-07-23 to reflect Phase 1 implementation (PR [#30](https://github.com/Josh-Uvi/DrawLift/pull/30) + [#31](https://github.com/Josh-Uvi/DrawLift/pull/31)). US-001 ✅ Done; US-002 → US-011 👀 In Review (US-003 🚧 In Progress — pre-commit hook pending).*