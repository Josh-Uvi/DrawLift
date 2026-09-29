<!--
Thanks for contributing! Fill in the sections below.
See CONTRIBUTING.md for the full workflow and required checks.
-->

## Summary

<!-- What does this change do, and why? -->

## Related issue

<!-- Use a closing keyword so the issue closes automatically -->
Closes #

## Type of change

- [ ] `feat` — new functionality
- [ ] `fix` — bug fix
- [ ] `docs` — documentation only
- [ ] `refactor` — behaviour-preserving change
- [ ] `chore` — tooling, CI, or dependencies
- [ ] `test` — tests only

## Affected areas

- [ ] Backend (`backend/`)
- [ ] Frontend (`frontend/`)
- [ ] Docs (`README.md`, `docs/`)
- [ ] Tooling / CI

## How to test

<!-- Exact commands a reviewer can run -->

```bash
make check   # lint + typecheck + test
make build   # backend byte-compile + frontend production build
```

## Checklist

- [ ] `make check` passes locally
- [ ] `make build` passes locally
- [ ] Commits are signed (required by the `main` ruleset)
- [ ] PR title follows Conventional Commits (`type(scope): summary`)
- [ ] Tests added or updated where behaviour changed
- [ ] Docs updated where relevant
- [ ] No secrets committed (talisman `pre-push` hook passed)
- [ ] Protected paths (`.github/**`, `migrations/**`, `**/.env*`, `*.env`) are approved by a maintainer
