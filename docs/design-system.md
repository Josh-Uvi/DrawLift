# Design System

The frontend is intentionally lightweight: Next.js App Router, TypeScript, TailwindCSS, and a small set of shared components.

## Product surfaces

| Surface | Path | Purpose |
| --- | --- | --- |
| Upload | `frontend/src/app/page.tsx` | Drop a PDF and configure conversion options. |
| Job detail | `frontend/src/app/jobs/[id]/page.tsx` | Show live progress, previews, errors, retry, and downloads. |
| History | `frontend/src/app/history/page.tsx` | List, filter, reopen, and delete jobs. |

## Tokens

Tailwind extensions in `frontend/tailwind.config.ts` define:

| Token | Value | Use |
| --- | --- | --- |
| `background` | `#0a0a0a` | Dark surfaces where used. |
| `foreground` | `#ededed` | Text on dark surfaces. |
| `primary` | `#3b82f6` | Primary buttons, focus rings, action states. |
| `accent` | `#8b5cf6` | Accent/highlight color. |

Global CSS in `frontend/src/app/globals.css` currently keeps a simple white page background and black text baseline.

## Shared components

### Button

`frontend/src/components/shared/Button.tsx`

Variants:

- `primary`
- `secondary`
- `outline`
- `ghost`

Sizes:

- `sm`
- `md`
- `lg`

The component includes rounded corners, focus rings, hover states, and disabled state styling.

### Card

`frontend/src/components/shared/Card.tsx`

A white, rounded, bordered panel with optional title. Used to group upload, job status, and history sections.

## Job-specific components

- `ProgressTracker`: progress/status UI backed by SSE and job polling.
- `PageViewer`: horizontal extracted-page thumbnail strip.
- `ImageModal`: enlarged page preview.
- `Model3DPreview`: GLB preview using Three.js and React Three Fiber.
- `DownloadButton`: output download actions.
- `RetryButton`: failed-job retry action.
- `JobTable`: history table with filtering and delete action.

## UX principles

- Keep conversion state explicit: uploaded, pending, processing, completed, failed, archived.
- Prefer actionable errors over raw stack traces in the UI; stack traces are retained in the backend model for debugging.
- Disable impossible actions: downloads before completion, retry for non-failed jobs, submit before selecting a file.
- Make generated artifacts visible: page previews for all parsed jobs and 3D preview for GLB-capable jobs.

## Accessibility guidelines

- Preserve native button semantics for shared actions.
- Maintain visible focus rings, especially around upload and job-management controls.
- Use text labels alongside icons or visual status colors.
- Ensure modals trap attention and can be dismissed predictably when expanded beyond the current implementation.
- Do not rely on color alone to distinguish job statuses.

## Future design work

- Consolidate status badges into a shared component.
- Document spacing, typography, and status colors as explicit tokens.
- Add empty, loading, and error states for each page.
- Add visual regression tests once the UI stabilizes.
