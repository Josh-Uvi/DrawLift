# API

The API is implemented by FastAPI under `backend/app/api/v1`. All paths below are relative to `/api/v1`.

## Authentication

There is no authentication in the current proof-of-concept. Treat every endpoint as single-user/local-development only until auth and per-user job isolation are added.

## Endpoints

| Method | Path | Success | Notes |
| --- | --- | --- | --- |
| `GET` | `/health` | `200` | Returns service health. |
| `POST` | `/jobs` | `201` | Multipart upload with `file` and JSON string `config`. |
| `GET` | `/jobs` | `200` | Supports `status`, `status_filter`, `page`, `limit`, `offset`. |
| `GET` | `/jobs/{job_id}` | `200` | Full job status model. |
| `GET` | `/jobs/{job_id}/stream` | `200` | SSE stream of `progress` events. |
| `GET` | `/jobs/{job_id}/pages/{page_number}` | `200` | Extracted page PNG, 1-based page number. |
| `GET` | `/jobs/{job_id}/download` | `200` | Requires completed job. Query `format=dxf`, `dwg`, or `glb`. |
| `POST` | `/jobs/{job_id}/retry` | `200` | Only failed jobs can be retried. |
| `DELETE` | `/jobs/{job_id}` | `204` | Deletes DB row and associated local storage directory. |

## Job config

`JobConfig` is validated by Pydantic in `backend/app/schemas/job.py`.

```json
{
  "mode": "2d",
  "dpi": 300,
  "floor_height_m": 3.0,
  "slab_thickness_m": 0.2,
  "include_ceiling": false,
  "output_format": "dxf",
  "segmenter": "classic"
}
```

Constraints:

- `mode`: `2d` or `3d`.
- `dpi`: 72 to 1200.
- `floor_height_m`: 0.5 to 10.0.
- `slab_thickness_m`: 0.05 to 2.0.
- `output_format`: `dxf`, `dwg`, or `both`.
- `segmenter`: `classic` or `ml`.

## Create a job

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -F 'file=@floorplan.pdf;type=application/pdf' \
  -F 'config={"mode":"3d","dpi":300,"floor_height_m":3.0,"output_format":"both","segmenter":"classic"}'
```

Response:

```json
{
  "job_id": "95cfb8c5-9c6b-4a2d-b26e-2ca94b80c6a1"
}
```

Validation behavior:

- Non-`.pdf` filenames return `400`.
- Non-`application/pdf` MIME types return `400` when the upload includes a content type.
- Invalid config JSON returns `400`.
- Config schema violations return `422`.

## Job status response

```json
{
  "id": "95cfb8c5-9c6b-4a2d-b26e-2ca94b80c6a1",
  "status": "processing",
  "progress": 60,
  "step": "Segmentation",
  "config": {
    "mode": "3d",
    "dpi": 300,
    "floor_height_m": 3.0,
    "slab_thickness_m": 0.2,
    "include_ceiling": false,
    "output_format": "both",
    "segmenter": "classic"
  },
  "input_file": "storage/95cf.../input.pdf",
  "output_file": null,
  "page_count": 2,
  "error_msg": null,
  "error_trace": null,
  "created_at": "2026-07-29T18:00:00Z",
  "updated_at": "2026-07-29T18:01:00Z"
}
```

## SSE progress

Subscribe from the browser with `EventSource`:

```text
GET /api/v1/jobs/{job_id}/stream
```

Event shape:

```text
event: progress
data: {"job_id":"95cf...","status":"processing","progress":80,"step":"Vectorization","message":"completed"}
```

The stream currently stops after a `completed` event. Failed jobs publish a `failed` event, and clients should also fetch the job details to display stored `error_msg` and retry actions.

## Downloads

```bash
curl -OJ 'http://localhost:8000/api/v1/jobs/{job_id}/download?format=dxf'
curl -OJ 'http://localhost:8000/api/v1/jobs/{job_id}/download?format=dwg'
curl -OJ 'http://localhost:8000/api/v1/jobs/{job_id}/download?format=glb'
```

Download returns `409` until the job is `completed`. DWG and GLB downloads require those artifacts to exist for the job.

## Page preview

Page numbers are 1-based:

```text
GET /api/v1/jobs/{job_id}/pages/1
```

The implementation uses allowlisted `page_0001.png` naming and path containment checks before serving files.
