# Trade-offs and Alternatives

This document captures the main decisions behind the current implementation and realistic alternatives for future versions.

## Python/FastAPI backend instead of Node.js

**Decision:** Use Python 3.11 with FastAPI for the backend.

**Why:** The conversion domain depends on PyMuPDF, OpenCV, NumPy, ONNX Runtime, ezdxf, trimesh, shapely, and related scientific/CAD tooling.

**Trade-off:** The stack is polyglot because the frontend is TypeScript.

**Alternative:** A Node.js API gateway with Python worker service. This can improve frontend/backend language consistency at the API layer but adds another service boundary.

## Celery over synchronous request handling

**Decision:** Run conversion in Celery tasks via Redis.

**Why:** PDF rendering, segmentation, vectorization, and conversion can exceed normal HTTP request timeouts.

**Trade-off:** Redis, worker processes, retries, and idempotency become operational concerns.

**Alternative:** Cloud queues and workers (SQS, Cloud Run Jobs, Kubernetes Jobs) for elastic production scaling.

## SSE over WebSockets

**Decision:** Use Server-Sent Events for progress updates.

**Why:** Progress is one-way from server to browser and SSE is simpler than WebSockets.

**Trade-off:** SSE is not suited to bidirectional collaboration or live editing.

**Alternative:** WebSockets if the product later adds live annotation, cancellation controls, or collaborative review.

## DXF primary, DWG optional

**Decision:** Generate DXF internally and convert to DWG only through an operator-supplied external command.

**Why:** DXF is open and well-supported by `ezdxf`; DWG is proprietary.

**Trade-off:** DWG quality and availability depend on the configured converter.

**Alternative:** License ODA tooling and build a first-class converter container, or keep DXF as the only supported CAD exchange format.

## Classic CV and ONNX segmentation

**Decision:** Support `classic` and `ml` segmenters.

**Why:** Classic CV is fast and predictable for simple line drawings. ONNX Runtime keeps ML inference deployable on CPU when a suitable model is configured.

**Trade-off:** Maintaining two segmentation modes increases test and tuning scope.

**Alternative:** Start with classic only for MVP, or make ML-only the product differentiator and invest in training data/model operations.

## Local filesystem storage

**Decision:** Store uploads and outputs in local volumes for this POC.

**Why:** It keeps development simple and makes Docker/hybrid workflows straightforward.

**Trade-off:** Local storage complicates horizontal scaling and data durability.

**Alternative:** S3-compatible object storage with signed URLs, lifecycle policies, and per-tenant prefixes.

## Next.js frontend

**Decision:** Use Next.js App Router with Tailwind and focused client components.

**Why:** It provides a familiar React structure, routing, API URL configuration, and production build path.

**Trade-off:** Some functionality is client-heavy because uploads, SSE, and 3D preview happen in the browser.

**Alternative:** A Vite SPA would be simpler for a purely client-rendered internal tool.

## PostgreSQL JSONB config

**Decision:** Persist job config as JSONB.

**Why:** Conversion settings evolve frequently and benefit from schema flexibility.

**Trade-off:** Strong typing is enforced at application boundaries rather than fully in the database.

**Alternative:** Normalize stable config fields into columns once the product contract stabilizes.
