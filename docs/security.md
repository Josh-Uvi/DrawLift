# Security

This document scopes current protections and realistic risks for DrawLift. The current app is best treated as a local/development proof-of-concept, not a hardened multi-tenant SaaS.

## Current controls

### Upload validation

- `POST /api/v1/jobs` requires a filename ending in `.pdf`.
- If an upload content type is present, it must be `application/pdf`.
- Conversion options are validated by Pydantic `JobConfig`.

### Path and file serving controls

- Page image serving constructs paths from configured storage and persisted job IDs.
- Page filenames are allowlisted with `page_0001.png` style matching.
- Path containment checks prevent serving files outside expected storage directories.
- Downloads require completed jobs and known formats (`dxf`, `dwg`, `glb`).

### Secrets and configuration

- Runtime settings are environment driven through `.env` / Compose environment.
- `.env.example` documents expected variables without real secrets.
- `.talismanrc` and pre-commit tooling are present for local quality and secret scanning workflows.

### Error handling

- Failed jobs store user-visible `error_msg` and backend `error_trace`.
- Global API error handling exists under `backend/app/api/errors.py`.
- Celery retries use exponential backoff, reducing transient-failure impact.

### File lifecycle

- Celery Beat cleanup archives jobs and removes storage files after `STORAGE_TTL_DAYS`.

## Key risks

| Risk | Why it matters | Current status | Recommended next step |
| --- | --- | --- | --- |
| No authentication | Any user with network access can view/delete jobs. | Accepted for POC. | Add auth and per-user job ownership. |
| Untrusted PDFs | PDFs can be malformed or resource-heavy. | Basic validation only. | Add size/page limits, malware scanning, and parser sandboxing. |
| Local storage | Files live on local/container volumes. | Fine for dev. | Use object storage with scoped credentials in production. |
| External DWG converter | Command execution depends on operator config. | Template command supported. | Strictly control converter binary, arguments, user, and container permissions. |
| Error traces | Stack traces may reveal internals. | Stored in DB and may be returned by API model. | Hide traces from non-admin users before multi-user deployment. |
| Dependency vulnerabilities | CV/ML/CAD libraries process complex binary data. | Dependencies pinned by broad version ranges. | Add Dependabot, lockfiles, image scanning, and regular updates. |

## Production hardening checklist

- [ ] Add authentication and authorization.
- [ ] Associate jobs with users or tenants.
- [ ] Enforce upload size, page count, and conversion time limits.
- [ ] Run PDF parsing/conversion in restricted containers with read-only roots where possible.
- [ ] Add antivirus/malware scanning for uploads.
- [ ] Move storage to S3-compatible object storage with lifecycle policies.
- [ ] Do not return `error_trace` to ordinary users.
- [ ] Add rate limiting and queue quotas.
- [ ] Restrict CORS to deployed frontend origins.
- [ ] Use non-default database credentials and managed secrets.
- [ ] Add structured audit logs for upload, download, retry, and delete actions.

## Security boundaries

DrawLift validates and manages files; it does not guarantee that generated CAD output is semantically correct or safe to use as construction documentation. Human review remains required before professional use.
