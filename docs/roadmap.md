# Roadmap

This roadmap distills `TODO.md` and `implementation_plan.md` into a concise delivery view. `TODO.md` remains the detailed user-story tracker.

## Current status

The project has implemented the core proof-of-concept path:

- Monorepo structure and tooling.
- Docker Compose stack for frontend, backend, worker, beat, PostgreSQL, and Redis.
- FastAPI health, job creation, job listing/detail, page serving, downloads, retry, and delete endpoints.
- PostgreSQL job metadata with Alembic migrations.
- Celery worker and Redis progress publishing.
- Next.js upload, job detail, history, page preview, 3D preview, retry, and download UI.
- Pipeline steps for PDF parsing, preprocessing, segmentation, vectorization, 3D extrusion, DXF writing, GLB writing, and optional DWG conversion.
- Cleanup/archive task for expired local files.

## Stages

| Stage | Goal | Status summary |
| --- | --- | --- |
| Stage 0 — Bootstrap | Repo, tooling, CI scaffold. | Implemented/in review in TODO history. |
| Phase 1 — MVP skeleton | Upload, queue, job tracking, placeholder flow. | Implemented. |
| Phase 2 — PDF parsing | Render and preview PDF pages. | Implemented. |
| Phase 3 — 2D vectorization | Segment/vectorize into DXF. | Implemented. |
| Phase 4 — 3D extrusion | Extrude walls/slabs and export GLB. | Implemented. |
| Phase 5 — Polish and DWG | DWG hook, history, retries, cleanup. | Implemented/in review. |

## Remaining product opportunities

### Conversion quality

- Add confidence scoring for segmentation and vectorization.
- Let users select pages before conversion.
- Add manual correction/annotation workflow.
- Add model evaluation data and regression fixtures.

### Operations

- Add queue metrics, job duration metrics, and failure classification.
- Add explicit job cancellation.
- Add object storage adapter.
- Add production deployment templates.

### Security and multi-tenancy

- Add authentication.
- Add per-user job isolation.
- Add upload scanning and hard limits.
- Hide stack traces from non-admin users.

### CAD/BIM outputs

- Improve DWG converter packaging guidance.
- Add IFC export only if BIM semantics become a product requirement.
- Add CAD-layer configuration and scale calibration.

## Definition of done for future work

A future story should be considered complete when:

- Acceptance criteria are checked.
- Backend tests and/or frontend checks cover the behavior.
- Docker or hybrid workflow is manually verified when runtime behavior changes.
- API, operations, or design docs are updated when relevant.
- The GitHub issue/PR links the work clearly.
