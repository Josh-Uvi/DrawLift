# Contributing

Thanks for contributing to **DrawLift** (AI File Converter). This guide covers the
workflow every change follows. For day-to-day commands see
[docs/operations.md](./docs/operations.md); for planned work see
[docs/TODO.md](./docs/TODO.md) and [docs/roadmap.md](./docs/roadmap.md).

## Prerequisites

| Tool | Version | Used for |
| --- | --- | --- |
| Python | 3.11 | backend (FastAPI, Celery, ML pipeline) |
| Node.js | 24 | frontend (Next.js) |
| Docker | current | PostgreSQL, Redis, Celery worker/beat, DWG sidecar |

## Local setup

```bash
make install   # backend virtualenv + Python deps, frontend npm deps
make help      # list every available target
```

Hybrid development runs the frontend and backend on the host while PostgreSQL,
Redis, and the Celery worker run in Docker:

```bash
make local-up
make local-status
make local-down
```

## Quality gates

Run these before opening a pull request.

| Command | Backend | Frontend |
| --- | --- | --- |
| `make lint` | `ruff check` + `ruff format --check` | `eslint` + `prettier --check` |
| `make typecheck` | `mypy app/` | `tsc --noEmit` |
| `make test` | `pytest` | `vitest` (when configured) |
| `make build` | `compileall` | `next build` |

```bash
make check   # lint + typecheck + test
make build   # backend byte-compile + frontend production build
```

Every command also accepts a per-project suffix (`make lint-frontend`). Phases may
be parallelised one phase at a time with `make -j2 lint`, but keep `install`,
`check`, and `build` sequential because `install` rewrites dependency directories.

## Branching

Use `<type>/<issue-number>-<short-description>` when the work belongs to an issue,
so GitHub links the branch and pull request automatically. Otherwise use
`<type>/<short-description>`.

```bash
git switch -c feat/12-monorepo-layout
git switch -c docs/contributing-and-pr-template
```

Never commit directly to `main`: a repository ruleset requires every change to
land through a pull request.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/).

```
type(scope): imperative summary

Body explaining what changed and why.
```

Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
Common scopes: `backend`, `frontend`, `ml`, `devops`, `make`, `docs`, `security`.

Commits must be **signed** — the `main` ruleset enforces `required_signatures`:

```bash
git config commit.gpgsign true
git config user.signingkey <your-key-id>
```

## Pull requests

```bash
git push -u origin <branch>
gh pr create --base main --fill
```

The template in [docs/pull_request_template.md](./docs/pull_request_template.md) is
loaded automatically. Fill in the summary, link the issue with `Closes #<number>`,
and list the commands you ran.

Required gates before merging:

| Requirement | Detail |
| --- | --- |
| Approving review | 1 required, from a code owner (`.github/CODEOWNERS`) |
| Stale reviews | dismissed when new commits are pushed |
| Review threads | all must be resolved |
| Status check | `CodeQL` must pass, with the branch up to date with `main` |

Squash, merge commit, and rebase merges are all allowed. Do not bypass these rules
with admin privileges, and do not force push to `main`.

## Protected paths

Changes under these paths need explicit maintainer approval (see
[agent.yaml](./agent.yaml)):

- `.github/**`
- `infrastructure/**`
- `secrets/**`
- `migrations/**`
- `**/.env*`, `*.env`

## Secrets

Never commit credentials. Backend configuration lives in `.env` (git-ignored);
`.env.example` documents the supported variables. The `talisman` `pre-push` hook
scans outgoing commits. If it reports a false positive on a documentation file,
refresh that file's checksum rather than bypassing the hook:

```bash
talisman --checksum <file>
```

Then update the matching entry in `.talismanrc`.

## Pre-commit hooks

```bash
pre-commit install        # from the repository root
pre-commit run --all-files
```

The hooks run backend `ruff` and `mypy` plus frontend `eslint` and `prettier`.
