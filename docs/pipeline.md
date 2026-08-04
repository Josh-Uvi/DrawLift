# Conversion Pipeline

The conversion pipeline runs in the Celery worker and is composed of ordered, pluggable steps from `backend/app/pipeline/steps`.

## Pipeline context

`PipelineContext` carries state between steps:

- `job_id`
- `input_path`
- `config`
- `page_images`
- `preprocessed`
- `masks`
- `primitives`
- `output_path`
- `metadata`
- `progress_publisher`

## Stages

```mermaid
flowchart TD
  PDF[PDF input] --> Parser[PdfParserStep\nPyMuPDF page PNGs]
  Parser --> Pre[OpenCVPreprocessor\ngrayscale, blur, threshold, deskew]
  Pre --> Seg[SegmenterStep\nclassic CV or ONNX]
  Seg --> Vec[VectorizerStep\nCAD primitives]
  Vec --> Mode{3D mode?}
  Mode -- yes --> Extrude[WallExtruderStep\nwalls and slabs]
  Mode -- no --> DXF[DxfWriterStep]
  Extrude --> DXF
  DXF --> GLB{3D mode?}
  GLB -- yes --> GlbWriterStep[GLB writer]
  GLB -- no --> DWG{DWG requested?}
  GlbWriterStep --> DWG
  DWG -- yes --> DwgConverterStep[External converter]
  DWG -- no --> Done[Completed job]
  DwgConverterStep --> Done
```

## Step responsibilities

| Step | File | Responsibility | Typical progress |
| --- | --- | --- | --- |
| PDF parsing | `pdf_parser.py` | Render each PDF page to PNG at configured DPI. | 20% |
| Preprocessing | `preprocessor.py` | Convert to grayscale/binary arrays, denoise, threshold, deskew. | 35% |
| Segmentation | `segmenter.py` | Produce masks for walls, doors, windows, rooms, and text. | 60% |
| Vectorization | `vectorizer.py` | Convert masks into wall/opening/room/text primitives. | 80% |
| 3D extrusion | `extruder.py` | Create wall solids and slab primitives for 3D jobs. | 85% |
| DXF writing | `dxf_writer.py` | Write layered 2D/3D DXF via `ezdxf`. | 95% |
| GLB writing | `glb_writer.py` | Export self-contained GLB for browser preview and download. | 97% |
| DWG conversion | `dwg_converter.py` | Run configured external converter command. | 98% |

## Progress reporting

The task publishes progress through Redis Pub/Sub on channel `job:{job_id}`:

1. `processing` / 0% / `Starting` as soon as the worker claims the job.
2. One event per step (see Typical progress above) as each step completes.
3. `completed` / 100% or `failed` with the error message as the terminal event.

The FastAPI SSE endpoint forwards these events and closes the stream on `completed` or `failed`. The job page also polls the REST API every 3 seconds, so progress stays visible even if the browser subscribed after some events were published.

The task also logs lifecycle lines (`Job {id}: starting conversion`, `running pipeline with N step(s)`, `pipeline completed successfully`, or `pipeline failed`) to the worker log.

## Output layers and artifacts

DXF outputs use domain-oriented layers such as:

- `WALLS`
- `DOORS`
- `WINDOWS`
- `ROOMS`
- `TEXT`
- `WALLS_3D`
- `SLABS`

3D jobs also produce `output.glb`. DWG jobs produce `output.dwg` only when `DWG_CONVERTER_COMMAND` is configured and succeeds.

## Segmenter options

- `classic`: deterministic OpenCV path. It is faster and suitable for simple, high-contrast line drawings.
- `ml`: ONNX Runtime path. It is intended for richer plans but depends on configured model files or model download settings.

## Edge cases handled or expected

- Multi-page PDFs write numbered page images and persist `page_count`.
- 3D-only fields are accepted in config even when mode is `2d`; they are ignored by non-3D steps.
- DWG conversion failures surface as failed jobs with `error_msg` and `error_trace`.
- Worker retries are configured with exponential backoff, but deterministic input/config errors will fail repeatedly until changed.

## Known limitations

- Output quality depends heavily on input drawing quality and segmentation accuracy.
- The current storage adapter is local filesystem oriented.
- True DWG generation is a post-processing conversion from DXF, not a native DWG writer.
- The pipeline is synchronous inside a Celery task; parallel page processing is a future optimization.
