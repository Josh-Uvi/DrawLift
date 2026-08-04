# Risks and Edge Cases

DrawLift operates in a domain where input quality varies widely. This document lists realistic risks and how the current project handles or should handle them.

## Input document risks

| Edge case | Impact | Current behavior | Future mitigation |
| --- | --- | --- | --- |
| Scanned low-resolution PDFs | Poor segmentation/vectorization. | Accepted if PDF validation passes. | Add quality warnings and recommended DPI guidance. |
| Very large PDFs | Slow rendering, high memory/disk use. | No explicit documented limit. | Enforce upload size, page count, pixel count, and timeout limits. |
| Rotated/skewed plans | Misaligned primitives. | Preprocessor includes deskew. | Add user rotation override and preview validation. |
| Mixed architectural sheets | Non-floor-plan pages may be parsed. | All pages are rendered. | Let users select pages before conversion. |
| Password-protected PDFs | Parser failure. | Failed job with error. | Detect earlier and return actionable upload error. |

## Conversion quality risks

- Walls may be fragmented when scans are noisy or line weights vary.
- Doors/windows can be confused with text or symbols.
- Room polygon detection can fail for open plans or incomplete boundaries.
- 3D extrusion assumes a simple floor height and does not infer stairs, roofs, structural systems, or BIM semantics.
- DXF/DWG outputs should be reviewed by a CAD professional before use.

## Operational risks

| Risk | Impact | Mitigation in project |
| --- | --- | --- |
| Worker crash mid-job | Job may stay processing until retried or manually inspected. | Celery retries and error persistence for raised exceptions. |
| Redis unavailable | Queue and SSE progress fail. | Docker health checks; no HA in POC. |
| PostgreSQL unavailable | API and worker cannot persist state. | Docker health checks; no HA in POC. |
| Storage path mismatch | API cannot serve worker outputs. | `portable_storage_path` supports hybrid host/Docker paths. |
| Cleanup deletes files | Historical jobs become archived and downloads unavailable. | TTL is explicit via `STORAGE_TTL_DAYS`. |

## API edge cases

- `GET /download` returns conflict before completion.
- Retry is allowed only for failed jobs.
- Page preview returns 404 when the page number exceeds `page_count` or image files are absent.
- Delete removes the job row and local files, so clients should handle stale job-detail pages.

## Product risks

- Users may expect DWG to be native; the current implementation converts from DXF through external tooling.
- Users may assume generated 3D is BIM-grade; current GLB/DXF 3D is geometric preview/export, not full BIM.
- No user accounts means history is global to the deployment.
- Lack of cancellation means expensive jobs continue once queued.

## Recommended next controls

1. Add upload and conversion limits.
2. Add job cancellation.
3. Add page selection before conversion.
4. Add quality scoring or confidence indicators.
5. Add admin/operator views for failed jobs and queue health.
6. Add structured metrics for duration, failure type, input size, and output size.
