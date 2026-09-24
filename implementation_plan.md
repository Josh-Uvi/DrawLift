# Implementation Plan — ✅ IMPLEMENTED (2026-09-24)

> Status: all 7 implementation steps completed locally. `M .github/workflows/project-sync.yml`
> validated (YAML OK, `bash -n` OK, criteria fixtures pass, token-gate passes;
> `shellcheck`/`actionlint` unavailable locally — skipped). Remaining: live E2E
> checklist (Testing step 5) runs on GitHub after merge.

## Overview

Rewrite `.github/workflows/project-sync.yml` to keep GitHub Project board cards in sync with issue/PR lifecycle events, replacing the hand-rolled `curl`+`jq`+GraphQL script with the official **GitHub CLI (`gh`)** — while fixing the verified bugs (dead keyword regex, broken acceptance-criteria return value, corrupted checkbox counting, non-paginated item lookup, silent-always-green error handling) and removing the self-triggering issue auto-close race.

Context established during analysis:

- The current keyword regex `(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)` uses non-capturing groups that GNU grep (what GitHub runners ship) rejects — reproduced in `ubuntu:24.04` / GNU grep 3.11: warnings, **zero matches, exit 1**. Both the `push` handler and the PR-closed linked-issue handler are dead code on runners.
- `check_acceptance_criteria` prints a diagnostic `echo` line that gets captured by `CRITERIA_RESULT=$(...)`, so the value is multi-line and never equals `done` — every closed issue lands in **In Review**, never **Done**.
- `grep -cE ... || echo 0` captures `"0\n0"` (grep -c prints 0 AND exits 1), breaking all `-eq` comparisons (verified by execution).
- `find_existing_item` scans only `items(first: 100)` (no pagination) → duplicate cards once the board exceeds 100 items.
- Every error path warns and exits 0; the job can never fail, misconfiguration is invisible; the advertised token "fallback" does not exist.
- The script closes issues itself via REST `PATCH`, which re-fires `issues:closed` and re-runs itself; there is no `concurrency:` control.
- `issues:edited` / `pull_request:edited` yank cards back to Todo/In Review on any body/title edit — undocumented and undesirable.

High-level approach: one job, one inline bash step using `gh` (preinstalled on `ubuntu-latest` runners, respects `GH_TOKEN`). Project metadata (project/field/option IDs) resolved with a single verified GraphQL query via `gh api graphql`; card operations done with `gh project item-list` (auto-paginating), `gh project item-add`, `gh project item-edit`; linked issues resolved with GraphQL `closingIssuesReferences` (GitHub's own resolver) instead of text-parsing; checkbox counting done with `awk` (no exit-code/count pitfalls). Strict-but-fair failure semantics: skip (exit 0) only when `PROJECT_TOKEN` is unset; any configured-but-failed API call fails the job (exit 1).

### Behavioral changes (assumptions — review before implementation)

1. **Remove the `push` trigger.** GitHub natively auto-closes linked issues when a `Closes/Fixes/Resolves #N` commit lands on the default branch; that auto-close fires `issues:closed`, which the issues branch already handles (criteria check → Done/In Review). The hand-rolled push handler therefore adds duplicate work and the self-trigger race; removing it eliminates both.
2. **Remove `edited` from both `issues` and `pull_request` triggers.** Edits should not reset card status; meaningful lifecycle events drive the board.
3. **PR closed-without-merge no longer treated as Done.** PR card → In Review; linked issues (found via `closingIssuesReferences`) revert to Todo.
4. **PR opened/reopened/synchronize also moves each closing-referenced issue to In Review** (propagates real work state), symmetric with the revert in (3).
5. **Remove the hand-rolled REST issue-close PATCH** (covered by (1)). Token permissions shrink to `contents: read` only (all project access goes through the PAT).

### New event → status matrix

| Event / action | Card / target |
|---|---|
| `issues.opened`, `issues.reopened` | Issue card → **Todo** |
| `issues.closed` | Issue card → **Done** (all checkboxes checked, or none present) else **In Review** |
| `pull_request.opened/reopened/synchronize` | PR card → **In Review**; each closing-referenced issue → **In Review** |
| `pull_request.closed` + merged | PR card → **Done** (linked issues handled by their auto-close `issues.closed` events) |
| `pull_request.closed` + not merged | PR card → **In Review**; each closing-referenced issue → **Todo** |
| `push` | No trigger (see assumption 1) |

## Types

Shell workflow — no compiled type system. Data contracts the script depends on:

1. **Workflow variables (env)** — `PROJECT_OWNER: string` (default `github.repository_owner`, overridable via repo variable `SYNC_PROJECT_OWNER`), `PROJECT_NUMBER: string` (default `"1"`, overridable via `SYNC_PROJECT_NUMBER`), `GH_TOKEN: string` (from `secrets.PROJECT_TOKEN`).
2. **Project metadata (GraphQL result, cached in globals)**:
   - `PROJECT_ID` — ProjectV2 node ID (`PVT_...`)
   - `STATUS_FIELD_ID` — ProjectV2SingleSelectField node ID named `Status`
   - `OPT_TODO`, `OPT_REVIEW`, `OPT_DONE` — single-select option IDs (strings; empty if the board lacks the option → script warns and exits 1)
   - Column vocabulary: `Todo`, `In Review`, `Done` (drop `In Progress` — currently fetched but never used).
3. **Event payload access** (via `$GITHUB_EVENT_PATH` + `jq`): `action`, `issue.number`, `pull_request.number`, `pull_request.merged`.
4. **`gh project item-list --format json` item shape** (used for find-by-content): `items[]` with `id` (item ID), `number` (content issue/PR number), `repository` (`owner/repo` string), `type` (`"Issue"` | `"PullRequest"`). ⚠ Confirm shape with a probe command during implementation; fallback is a paginated GraphQL `items(first:100, after:$cursor)` query if `gh` output lacks these fields.
5. **`gh project item-add --format json` output**: `{ "id": "<item ID>" }` — if content is already on the board this may return the existing item or an error; `ensure_item` handles both via a find-first strategy.
6. **`closingIssuesReferences` GraphQL shape**: `repository(owner:.., name:..){ pullRequest(number:..){ closingIssuesReferences(first:20){ nodes { number } } } }` → array of issue numbers.
7. **Criteria verdict**: single token on stdout — `done` | `review` (all diagnostics go to stderr).


## Files

| File | Action | Purpose |
|---|---|---|
| `/Users/joshuvi/Dev/poc/ai-file-converter/.github/workflows/project-sync.yml` | **Full rewrite (overwrite — the only file changed)** | New `gh`-CLI-based workflow. Structure below. |

No files created, deleted, or moved elsewhere. No repo-config changes required beyond: existing `PROJECT_TOKEN` secret (already referenced) and optional repo variables `SYNC_PROJECT_NUMBER` / `SYNC_PROJECT_OWNER`.

### New workflow skeleton

```yaml
name: Project Sync
on:
  issues:
    types: [opened, reopened, closed]
  pull_request:
    types: [opened, reopened, closed, synchronize]
permissions:
  contents: read
concurrency:
  group: project-sync-${{ github.event_name }}-${{ github.event.issue.number || github.event.pull_request.number || github.run_id }}
  cancel-in-progress: false
jobs:
  sync-project:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    env:
      GH_TOKEN: ${{ secrets.PROJECT_TOKEN }}
      PROJECT_OWNER: ${{ vars.SYNC_PROJECT_OWNER || github.repository_owner }}
      PROJECT_NUMBER: ${{ vars.SYNC_PROJECT_NUMBER || '1' }}
    steps:
      - name: Sync issue/PR to project board
        run: |
          <bash script — see Functions section>
```

## Functions

All functions live in the single inline `run:` block of `/Users/joshuvi/Dev/poc/ai-file-converter/.github/workflows/project-sync.yml`. Conventions: stdout carries only return values; all diagnostics go to stderr via `log`; failures call `die`. Shell flags: `set -uo pipefail` (no `-e`, so grep/jq non-zero exits in pipelines don't abort spuriously; every critical command gets explicit error handling).

### New / rewritten functions (1–6 of 12)

1. **`log`** — prints to stderr (`>&2`), keeps stdout clean for command substitution.
2. **`die`** — logs an `::error::` annotation and `exit 1`. Replaces every silent `exit 0` after a real failure.
3. **`gql`** — wraps `gh api graphql -f query=... -F var=...`, returns raw JSON; dies on GraphQL errors.
4. **`resolve_project_metadata`** — one GraphQL call: `user(login:$owner){ projectV2(number:$n){ id fields(first:50){ nodes { ... on ProjectV2SingleSelectField { id name options { id name } } } } } }` (with an `organization(login:$owner)` retry if `user` returns nothing, so a future org-owned project doesn't break it). Sets globals `PROJECT_ID`, `STATUS_FIELD_ID`, `OPT_TODO`, `OPT_REVIEW`, `OPT_DONE`. Dies if project, `Status` field, or any of the three options is missing — with a hint to set a PAT with `project` scope on auth errors.
5. **`criteria_status <issue-number>`** — `gh api "repos/$GITHUB_REPOSITORY/issues/$N" --jq .body`, then counts via `awk`:
   ```bash
   total=$(printf '%s\n' "$body" | awk '/^[[:space:]]*- \[[ xX]\]/{n++} END{print n+0}')
   unchecked=$(printf '%s\n' "$body" | awk '/^[[:space:]]*- \[ \]/{n++} END{print n+0}')
   ```
   Prints `done` (0 total or 0 unchecked) else `review` on **stdout only**; counts logged to stderr. No `grep -c`, no `|| echo 0`, no interleaved echoes — fixes the two verified criteria bugs.
6. **`find_item_id <number> <Issue|PullRequest>`** — `gh project item-list "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --limit 500 --format json` piped to `jq -r --argjson n "$n" --arg repo "$GITHUB_REPOSITORY" --arg t "$type" '.items[] | select(.number == $n and .repository == $repo and .type == $t) | .id' | head -1`. Auto-paginating → fixes the >100-card duplicate bug. Empty stdout = not found (not an error). ⚠ Probe the JSON shape once during implementation against the live project; if `number`/`repository`/`type` are absent, fall back to a paginated GraphQL `items(first:100, after:$cursor)` query (noted inline).

### New / rewritten functions (7–12 of 12)

7. **`add_item <url>`** — `gh project item-add "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --url "$url" --format json --jq .id`; dies on failure.
8. **`ensure_item <number> <type>`** — calls `find_item_id`; if empty, `add_item "https://github.com/$GITHUB_REPOSITORY/issues/$number"` (this URL form works for PRs too); prints item ID on stdout.
9. **`set_status <item-id> <option-id>`** — `gh project item-edit --id "$item" --project-id "$PROJECT_ID" --field-id "$STATUS_FIELD_ID" --single-select-option-id "$option"`; dies on non-zero exit or error output.
10. **`move_card <number> <type> <option-id>`** — `item=$(ensure_item "$number" "$type")` then `set_status "$item" "$option"`; logs `#<number> (<type>) → <status>`. The single entry point every branch uses.
11. **`closing_issue_numbers <pr-number>`** — GraphQL `repository(owner:$o, name:$r){ pullRequest(number:$n){ closingIssuesReferences(first:20){ nodes { number } } } }` → `jq -r '.data.repository.pullRequest.closingIssuesReferences.nodes[].number' | sort -un`. Replaces both dead regex paths with GitHub's own link resolution.
12. **`main` dispatch (rewritten tail)**:
    - Guard: `[ -n "$GH_TOKEN" ] || { echo "::warning::PROJECT_TOKEN secret not set — skipping project sync"; exit 0; }`
    - `resolve_project_metadata`
    - Read event fields from `$GITHUB_EVENT_PATH` via `jq -r '.action // empty'`, `.issue.number // empty`, `.pull_request.number // empty`, `.pull_request.merged // false`.
    - **`issues`**: `closed` → `verdict=$(criteria_status "$NUM")` → `OPT_DONE` if `done` else `OPT_REVIEW`; `opened`/`reopened` → `OPT_TODO`; then `move_card "$NUM" Issue "$OPT"`.
    - **`pull_request`**: opened-family (`opened|reopened|synchronize`) → `move_card "$PR_NUM" PullRequest "$OPT_REVIEW"`, then `for n in $(closing_issue_numbers "$PR_NUM"); do move_card "$n" Issue "$OPT_REVIEW"; done`.
    - `closed` + `merged=true` → `move_card "$PR_NUM" PullRequest "$OPT_DONE"` (linked issues are handled by their own auto-close `issues.closed` events).
    - `closed` + not merged → `move_card "$PR_NUM" PullRequest "$OPT_REVIEW"`, then loop `closing_issue_numbers` → `move_card "$n" Issue "$OPT_TODO"`.
    - Unknown event/action → log + exit 0.
    - End: `log "Project sync complete"`.

### Removed code (from current file)

| Removed | Replacement / migration |
|---|---|
| `graphql()` curl wrapper | `gql()` via `gh api graphql` |
| `add_to_project()` | `add_item()` via `gh project item-add` |
| `find_existing_item()` (first-100-only GraphQL) | `find_item_id()` via paginating `gh project item-list` |
| `set_status()` curl mutation | `set_status()` via `gh project item-edit` |
| `check_acceptance_criteria()` (polluted stdout, grep -c bug) | `criteria_status()` (stdout-only contract, awk) |
| `get_opt()` | folded into `resolve_project_metadata` |
| push-event commit-message parsing loop + REST `PATCH` issue-close | removed entirely (GitHub auto-closes linked issues on default-branch commits; `issues.closed` event then moves the card) |
| `COL_PROGRESS` / `OPT_PROGRESS` | dropped (never used) |

## Classes

Not applicable — shell workflow, no OOP. All reusable logic is the shell functions enumerated in the Functions section.

## Dependencies

- **No new packages or third-party actions added.** `gh`, `jq`, `bash`, `awk` are preinstalled on `ubuntu-latest` runners (matches the repo's existing no-action-pinning approach in `ci.yml`, which uses `actions/checkout@v4` etc. — no actions needed here at all since no repo files are read).
- Removes all raw `curl` usage from this workflow.
- Deliberately avoids Node-based actions (keeps the file's stated goal: no Node 20 deprecation warnings).
- Secrets/vars consumed: `secrets.PROJECT_TOKEN` (existing), optional `vars.SYNC_PROJECT_NUMBER`, `vars.SYNC_PROJECT_OWNER` (new; both have defaults matching today's hard-coded `1` / `Josh-Uvi`).



## Testing

No CI-style test framework exists for workflows in this repo (`.github/workflows/` has no companion tests), so validation combines static checks, local function tests, and a post-merge live checklist:

1. **YAML validity** — parse the rewritten file with PyYAML (Python available per `ci.yml` toolchain):
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('/Users/joshuvi/Dev/poc/ai-file-converter/.github/workflows/project-sync.yml')); print('YAML OK')"
   ```
   Also run `actionlint` if installed locally (`command -v actionlint`), otherwise note it for the user to run before/after merge.
2. **shellcheck on the embedded script** — the inline `run:` block uses `${{ }}` only in the YAML `env:` map (never inside the script text), so it can be extracted with PyYAML (neutralizing `!`-tags) and linted:
   ```bash
   python3 - <<'PY' > /tmp/project-sync-script.sh
   import yaml
   class L(yaml.SafeLoader): pass
   L.add_constructor(None, lambda l, n: None)
   wf = yaml.load(open('/Users/joshuvi/Dev/poc/ai-file-converter/.github/workflows/project-sync.yml'), L)
   print(wf['jobs']['sync-project']['steps'][0]['run'])
   PY
   shellcheck -s bash /tmp/project-sync-script.sh   # if shellcheck not installed: brew install shellcheck or skip with note
   ```
3. **Local unit test of the criteria logic** — extract the awk counting lines and run them against fixture bodies (all-checked, partial, none, edge `- [X]` no space, nested indentation) asserting `done`/`review` verdicts; mirrors the verified-failure cases of the old code.
4. **`gate` semantics test** — simulate empty `GH_TOKEN` locally (run the extracted script with `GH_TOKEN=` unset) and assert it exits 0 with the skip warning, never calling the API.
5. **Live behavior checklist (post-merge, GitHub-side)** — because real board mutations require the `PROJECT_TOKEN` secret, E2E happens on GitHub after merging:
   | # | Action | Expected card movement |
   |---|---|---|
   | 1 | Open issue (no checkboxes) | → Todo |
   | 2 | Open issue with 2 checkboxes, check 1 | → Todo |
   | 3 | Open PR with `Closes #<issue>` in body | PR → In Review, issue → In Review |
   | 4 | Push new commit to the PR (`synchronize`) | PR stays In Review (no duplicate card) |
   | 5 | Merge PR (all checkboxes checked) | PR → Done; issue auto-closes → Done |
   | 6 | Merge PR with 1 unchecked checkbox | issue auto-closes → In Review |
   | 7 | Close a PR without merging | PR → In Review; linked issue → Todo |
   | 8 | Re-run any event | no duplicate cards (find-first `ensure_item`) |
   Also verify a run with the `PROJECT_TOKEN` secret removed fails the job (red) only when the token is present-but-invalid, and skips (yellow warning, green job) when unset.
6. **Optional live probe during implementation** — if the user's local `gh` is authed with a token that has `project` scope, probe once to confirm `gh project item-list --format json` field names (`number`, `repository`, `type`, `id`) and adjust the `jq` filter before finalizing; otherwise the GraphQL fallback in `find_item_id` covers it.

## Implementation Order — ✅ done (2026-09-24)

Single-file change, ordered to keep the file valid at each checkpoint
(all steps executed; file is `M .github/workflows/project-sync.yml`):

- [x] 1. **Rewrite YAML scaffolding**
- [x] 2. **Write helper layer** (`set -uo pipefail`, `log`, `die`, `gql`, token guard)
- [x] 3. **Write project-metadata layer** (`resolve_project_metadata`, user → org fallback)
- [x] 4. **Write card-ops layer** (`criteria_status`, `find_item_id` + GraphQL fallback, `add_item`, `ensure_item`, `set_status`, `move_card`, `closing_issue_numbers`)
- [x] 5. **Write dispatch layer** (4 branches + final log line)
- [x] 6. **Validate locally**: PyYAML parse OK, `bash -n` OK, criteria fixtures
  (all-checked→`done`, partial→`review`, none→`done`, edge-indent→`review`),
  empty-token gate exits 0 with skip warning; `shellcheck`/`actionlint` skipped (not installed);
  confirmed no `curl` invocations, no `edited`/`push` triggers, header comment matches behavior.
- [x] 7. **Final review pass**: no `curl` commands (2 comment mentions only), no old
  functions (`get_opt`, `check_acceptance_criteria`, `find_existing_item`,
  `add_to_project`, `PATCH` — comment mentions only); `jq` filters follow the
  probable `gh` JSON shape with a paginated GraphQL fallback in `find_item_id`.
  Live E2E (Testing step 5) executes after the user merges.

Original order (kept for reference):

Single-file change, ordered to keep the file valid at each checkpoint:

1. **Rewrite YAML scaffolding** of `/Users/joshuvi/Dev/poc/ai-file-converter/.github/workflows/project-sync.yml`: updated header comment (documents new matrix + assumptions), new `on:` (drop `push`, drop `edited`), `permissions: contents: read`, `concurrency`, `timeout-minutes: 5`, env map with `GH_TOKEN`/`PROJECT_OWNER`/`PROJECT_NUMBER` (vars + defaults).
2. **Write helper layer** in the `run:` block: `set -uo pipefail`, `log`, `die`, `gql`, token guard.
3. **Write project-metadata layer**: `resolve_project_metadata` (user → org fallback, option validation, auth-error hint).
4. **Write card-ops layer**: `criteria_status`, `find_item_id`, `add_item`, `ensure_item`, `set_status`, `move_card`, `closing_issue_numbers`.
5. **Write dispatch layer**: event/action parsing + the four branches (issues closed, issues open-family, PR open-family, PR closed merged/unmerged) ending in a final log line.
6. **Validate locally** (Testing steps 1–4): PyYAML parse, shellcheck (or noted skip), criteria fixtures, empty-token gate test; fix any findings.
7. **Final review pass**: confirm no `curl` remains, no `edited`/`push` triggers, header comment matches behavior, jq filters match probed/probable `gh` JSON shapes; then stop for user review — live E2E (Testing step 5) executes after the user merges.