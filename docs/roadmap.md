# Roadmap

This roadmap is the distilled delivery view of DrawLift's path from proof-of-concept to a production-ready SaaS product. It distills `TODO.md` — the detailed user-story tracker — and every project document into staged outcomes. Every outstanding item traces back to findings in: [API](./api.md) · [Architecture](./architecture.md) · [Security](./security.md) · [Risks and edge cases](./risks-and-edge-cases.md) · [Trade-offs and alternatives](./trade-offs-and-alternatives.md) · [Pipeline](./pipeline.md) · [Operations](./operations.md) · [Design system](./design-system.md).

## Current status

The project has delivered the complete proof-of-concept (Stages 0–6, US-001 → US-032, all implemented/merged):

- Monorepo structure and tooling, CI (lint + Docker build), pre-commit quality gates.
- Docker Compose stack: frontend, backend, worker, beat, PostgreSQL, Redis, optional GNU LibreDWG sidecar.
- FastAPI: upload, job listing/detail, SSE progress, page serving, downloads, retry, delete.
- PostgreSQL job metadata with Alembic; Celery worker with Redis Pub/Sub progress events.
- Next.js: dropzone upload, conversion options, live progress, page thumbnails, GLB 3D preview, filterable history, retry, downloads.
- Pipeline: PyMuPDF parsing → OpenCV preprocessing → classic or ML (Yytsi Torch safetensors) segmentation → vectorization → 3D extrusion → ezdxf DXF → trimesh GLB → LibreDWG DWG conversion.
- Lifecycle: TTL cleanup/archive beat task and stale-job sweeper.

**The app is not yet a multi-tenant SaaS**: it has no authentication, no billing, local file storage, and developer-oriented runtime defaults. Stages 7–8 below close that gap.

## Production readiness findings

Each row names the gap, why it blocks a production SaaS, the source document, and the scheduled user story that closes it.

| Gap | Why it blocks production SaaS | Source | Story |
| --- | --- | --- | --- |
| No authentication / tenancy | Anyone can view or delete any job; no user concept at all | `api.md` (Authentication), `security.md` | US-033, US-034 |
| Stack traces exposed | `error_trace` is returned to every caller | `security.md` risk table | US-035 |
| No upload limits | Unbounded size/pages and encrypted PDFs create cost and DoS exposure | `security.md` hardening checklist, `risks-and-edge-cases.md` | US-036 |
| No rate limiting / fairness | One user can monopolize the queue | `risks-and-edge-cases.md` product risks | US-037 |
| No malware scanning | Untrusted PDFs processed on shared infrastructure | `security.md` hardening checklist | US-038 |
| Local-only storage | Blocks horizontal scaling and durability | `trade-offs-and-alternatives.md` (Local filesystem storage) | US-039 |
| No metrics, dashboards, or alerts | Cannot operate, debug, or alert at scale | `risks-and-edge-cases.md` recommended controls | US-040 |
| No job cancellation | Expensive jobs run to completion once queued | `risks-and-edge-cases.md` product risks | US-041 |
| Developer-oriented containers | Source bind mounts, `--reload`, default credentials are dev conveniences | `operations.md`, `security.md` | US-042 |
| No release pipeline / deps safety | No image publishing, Dependabot, or vulnerability scanning | `security.md` dependency exposures row | US-043 |
| No audit, retention, or compliance | GDPR-style obligations and trust requirements unmet | `security.md` hardening checklist | US-044 |
| No plans / entitlements | The service has no product limits or tiers | not yet documented | US-045 |
| No billing / subscriptions | The product cannot monetize | not yet documented | US-046 |
| No usage metering or quota visibility | Users cannot self-manage against limits | not yet documented | US-047 |
| No account dashboard | Users cannot self-serve profile, plan, or history | `design-system.md` product surfaces | US-048 |
| No landing / onboarding / pricing | The product has no acquisition surface | not yet documented | US-049 |
| Thin upload/progress UX | No upload progress bar, ETA hints, or guided failure recovery | `design-system.md` UX principles | US-050 |
| No page selection | Mixed drawing sheets waste budget and degrade output | `risks-and-edge-cases.md` (mixed architectural sheets) | US-051 |
| Inconsistent states & accessibility | Ad-hoc badges; sparse empty/loading/error states | `design-system.md` future design work | US-052 |
| No completion notifications | Users must babysit jobs to learn outcomes | product gap | US-053 |
| Reference-only ML weights | Conversion quality is not production-grade | `pipeline.md` known limitations | US-054 |
| Limited download UX | No artifact availability listing or bundled download | product gap | US-055 |
| No launch checklist or runbook | No day-2 operating model for deployment | `operations.md` troubleshooting table | US-056 |


## Stage view

| # | Stage / Milestone | Goal | Stories | Status |
| --- | --- | --- | --- | --- |
| 0 | Bootstrap | Repo, tooling, CI scaffold | US-001 → US-004 | ✅ Done |
| 1 | Phase 1 — MVP Skeleton | Upload + queue + job tracking | US-005 → US-011 | ✅ Done |
| 2 | Phase 2 — PDF Parsing | Page extraction and preview | US-012 → US-015 | ✅ Done |
| 3 | Phase 3 — 2D Vectorization | PDF → DXF core value | US-016 → US-020 | ✅ Done |
| 4 | Phase 4 — 3D Extrusion | Walls → 3D model + GLB | US-021 → US-024 | ✅ Done |
| 5 | Phase 5 — Polish & DWG | DWG hook, history, retries, cleanup | US-025 → US-028 | ✅ Done |
| 6 | ML Model & DWG | ML model provisioning + LibreDWG sidecar | US-029 → US-032 | ✅ Done |
| **7** | **Production Core** | **Security, multi-tenancy, storage, observability, deployment** | **US-033 → US-044** | 🟦 Todo |
| **8** | **SaaS Product & Billing** | **Plans, Stripe, metering, experience, launch** | **US-045 → US-056** | 🟦 Todo |

## Stage 7 — Production Core

Milestone: `Stage 7: Production Core` (due 2027-03-31). Goal: make the platform safe to expose to real, paying users. Suggested order: identity first (US-033/US-034), then P0 hardening (US-036/US-042), then the P1 cluster, P2 items as capacity allows.

### Epic 7.1 — Identity and multi-tenancy

- **US-033 · Account creation and sign-in** — P0 · M — Outcome: email+password auth (Argon2), short-lived tokens + httpOnly refresh, `GET /me`, 401 on every `/jobs*` endpoint for anonymous callers, `/login` and `/register` pages with validation and loading states. Closes the #1 row of the `security.md` risk table. · [Issue #60](https://github.com/Josh-Uvi/DrawLift/issues/60)
- **US-034 · Per-user job isolation** — P0 · M — Outcome: `jobs.user_id` ownership enforced on list/detail/pages/download/retry/delete (404 for foreign jobs), admin bypass for operators, user-scoped history, explicit handling of legacy pre-tenant rows. · [Issue #61](https://github.com/Josh-Uvi/DrawLift/issues/61)

### Epic 7.2 — Security hardening

- **US-035 · Hide stack traces** — P1 · S — Outcome: `error_trace` admin/debug-only; friendly error catalog drives user-facing `error_msg`. · [Issue #62](https://github.com/Josh-Uvi/DrawLift/issues/62)
- **US-036 · Upload limits and actionable rejections** — P0 · M — Outcome: 50 MB / 20-page defaults, encrypted-PDF detection, magic-byte sniffing, limits documented and surfaced in the upload UI. · [Issue #63](https://github.com/Josh-Uvi/DrawLift/issues/63)
- **US-037 · Rate limiting and fairness** — P1 · M — Outcome: Redis-backed per-user upload rate limits (429 + `Retry-After`) and active-job concurrency caps with clear messaging. · [Issue #64](https://github.com/Josh-Uvi/DrawLift/issues/64)
- **US-038 · Malware scanning** — P2 · M — Outcome: optional ClamAV sidecar with fail-open/fail-closed policy and EICAR-tested behavior. · [Issue #65](https://github.com/Josh-Uvi/DrawLift/issues/65)

### Epic 7.3 — Storage, observability, and control

- **US-039 · S3-compatible object storage** — P1 · L — Outcome: `StorageBackend` protocol, S3 adapter, presigned download URLs, TTL/lifecycle guidance; hybrid dev workflow unchanged. · [Issue #66](https://github.com/Josh-Uvi/DrawLift/issues/66)
- **US-040 · Metrics, logs, dashboards** — P1 · L — Outcome: Prometheus `/metrics` (uploads, queue depth, durations, failure classes), structured request-id logs, Grafana profile, documented alert rules. Enables the queue/failure metrics called for by `risks-and-edge-cases.md`. · [Issue #67](https://github.com/Josh-Uvi/DrawLift/issues/67)
- **US-041 · Job cancellation** — P1 · M — Outcome: cancel endpoint + cooperative pipeline checks; `cancelled` terminal status across API, SSE, history, and job page. · [Issue #68](https://github.com/Josh-Uvi/DrawLift/issues/68)

### Epic 7.4 — Deployment and compliance

- **US-042 · Hardened production runtime** — P0 · L — Outcome: non-root slim images, `docker-compose.prod.yml` with limits/restarts/healthchecks, TLS termination example, no default credentials, Trivy scan in CI. · [Issue #69](https://github.com/Josh-Uvi/DrawLift/issues/69)
- **US-043 · CI/CD and dependency safety** — P1 · M — Outcome: GHCR image publishing on tags, migration deploy step with rollback guidance, Dependabot (pip/npm/Docker/actions), CodeQL + secret scanning, coverage artifacts. · [Issue #70](https://github.com/Josh-Uvi/DrawLift/issues/70)
- **US-044 · Audit trails, retention, legal basics** — P2 · M — Outcome: audit log for mutating actions, self-service data export and account deletion, retention honoring TTL, placeholder Privacy/Terms pages. · [Issue #71](https://github.com/Josh-Uvi/DrawLift/issues/71)


## Stage 8 — SaaS Product & Billing

Milestone: `Stage 8: SaaS Product & Billing` (due 2027-06-30). Goal: turn the hardened platform into a sellable, self-serve product with a high-quality experience. Suggested order: entitlements (US-045) → Stripe (US-046) → metering (US-047), with the experience stories in parallel.

### Epic 8.1 — Monetization

- **US-045 · Plans and entitlements** — P0 · M — Outcome: Free/Pro plans as code-driven config (upload MB, pages/month, concurrent jobs, output formats, segmenters); enforced at job creation and download; `GET /entitlements` powers frontend gating. · [Issue #72](https://github.com/Josh-Uvi/DrawLift/issues/72)
- **US-046 · Stripe subscriptions** — P0 · L — Outcome: customer linking, Checkout, signature-verified idempotent webhooks, `subscriptions` table driving entitlements, Customer Portal for plan management. · [Issue #73](https://github.com/Josh-Uvi/DrawLift/issues/73)
- **US-047 · Usage metering and quota visibility** — P1 · M — Outcome: monthly page counters, budget checks with upgrade hints (429), `GET /usage`, upload-form hints, and account usage bars. · [Issue #74](https://github.com/Josh-Uvi/DrawLift/issues/74)

### Epic 8.2 — Account, onboarding, and experience

- **US-048 · Account dashboard** — P1 · M — Outcome: `/account` with profile/change-password, plan & usage cards, paginated + searchable history, auth-gated access. · [Issue #75](https://github.com/Josh-Uvi/DrawLift/issues/75)
- **US-049 · Landing and onboarding** — P1 · M — Outcome: hero, 3-step how-it-works, sample outputs, pricing driven by entitlements, auth CTAs, legal footer, gated upload entry with first-run guidance. · [Issue #76](https://github.com/Josh-Uvi/DrawLift/issues/76)
- **US-050 · Upload and progress confidence** — P1 · M — Outcome: XHR upload progress bar, client-side validation from entitlements, step name/percentage/ETA in the tracker, friendly failures with suggested next actions, cancel integration. · [Issue #77](https://github.com/Josh-Uvi/DrawLift/issues/77)
- **US-051 · Page selection before conversion** — P1 · M — Outcome: page thumbnails with select all/none, validated `config.pages`, worker honors selection, actionable 422s — closes the "mixed architectural sheets" risk row. · [Issue #78](https://github.com/Josh-Uvi/DrawLift/issues/78)

### Epic 8.3 — Quality, notifications, and launch

- **US-052 · Polished states and accessibility** — P2 · M — Outcome: shared `StatusBadge`, skeletons, empty states with CTAs, recoverable errors; a11y pass (focus, ARIA, keyboard-satisfiable modals, contrast); status tokens documented in the design system. · [Issue #79](https://github.com/Josh-Uvi/DrawLift/issues/79)
- **US-053 · Email notifications** — P2 · M — Outcome: console/SMTP notifier, tokenized time-limited download links, per-user toggle, failure-isolated delivery. · [Issue #80](https://github.com/Josh-Uvi/DrawLift/issues/80)
- **US-054 · Trained weights and evaluation harness** — P1 · L — Outcome: trained-weights candidates converted to the 5-class contract, `make validate-model` regression fixtures with per-class IoU, refreshed measured comparison in `pipeline.md`. Closes the primary `pipeline.md` quality limitation. · [Issue #81](https://github.com/Josh-Uvi/DrawLift/issues/81)
- **US-055 · One-click all-artifact downloads** — P2 · S — Outcome: `?format=zip` bundle with availability listing, explained-disabled buttons, informative filenames. · [Issue #82](https://github.com/Josh-Uvi/DrawLift/issues/82)
- **US-056 · Launch checklist and day-2 runbook** — P3 · S — Outcome: `launch-checklist.md` (DNS/TLS, secrets, backups, DR, monitoring, limits, support) and `runbook.md` (stuck queue, OOM worker, webhook replay, storage errors), linked from README. · [Issue #83](https://github.com/Josh-Uvi/DrawLift/issues/83)

## Deferred opportunities (beyond current staging)

Carried forward from prior roadmap iterations; intentionally not scheduled until the stages above land:

- Confidence scoring for segmentation/vectorization (awaiting US-054 harness).
- Manual correction/annotation workflow and scale calibration (CAD pro features).
- IFC/BIM export — only if BIM semantics become a product requirement.
- Horizontal worker autoscaling and queue priorities (post-launch scaling).
- Visual regression tests once the UI stabilizes (`design-system.md`).
- DWG alternative targets benchmarking (newer DWG revisions via other tooling).

## Definition of done

A story in Stages 7–8 is complete when:

- All acceptance criteria are checked on the GitHub issue.
- Backend tests and/or frontend checks cover the behavior (lint + build green).
- Docker or hybrid workflow is manually verified when runtime behavior changes.
- API, security, operations, pipeline, or design docs are updated where relevant.
- The GitHub issue/PR links the work and `project-sync` moves the card to Done.

_Document version 2.0 — updated 2026-08-25: production-SaaS roadmap added. Stages 7 (US-033 → US-044) and 8 (US-045 → US-056) planned and registered as GitHub issues; see `TODO.md` for full story detail._

