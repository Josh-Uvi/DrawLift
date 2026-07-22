#!/usr/bin/env bash
# scripts/bootstrap-github.sh
# ------------------------------------------------------------------------------
# One-shot bootstrap script for the AI File Converter (PDF -> DWG) project.
# Creates labels, milestones, the parent tracking issue, and a GitHub Project
# board with status columns. Safe to re-run; existing resources are skipped.
#
# Usage:
#   chmod +x scripts/bootstrap-github.sh
#   ./scripts/bootstrap-github.sh
#
# Requires: gh CLI v2.30+ authenticated with scopes: repo, project, read:org.
# ------------------------------------------------------------------------------
set -euo pipefail

REPO="${REPO:-Josh-Uvi/DrawLift}"
OWNER="${OWNER:-Josh-Uvi}"
PROJECT_TITLE="${PROJECT_TITLE:-AI File Converter}"

echo "==> Bootstrapping GitHub project for $REPO"

# ---------------------------------------------------------------------------
# 1. Labels
# ---------------------------------------------------------------------------
echo "--> Creating labels"
declare -a LABELS=(
  "area:frontend|1D76DB|Frontend (Next.js) code"
  "area:backend|5319E7|Backend (FastAPI / Celery) code"
  "area:devops|BFD4F2|Docker, CI/CD, infra"
  "area:ml|FBCA04|ML models, inference, training"
  "area:docs|0E8A16|Documentation only"
  "type:bug|D73A4A|Defect / regression"
  "type:chore|CCCCCC|Maintenance / refactor"
  "type:spike|F9D0C4|Investigation / research"
  "type:feature|A2EEEF|New user-facing capability"
  "epic:p0-bootstrap|C5DEF5|Stage 0 - Bootstrap and Tooling"
  "epic:p1-scaffold|BFD4F2|Stage 1 - MVP Skeleton"
  "epic:p2-pdf|BFDADC|Stage 2 - PDF Parsing"
  "epic:p3-vectorize|D4C5F9|Stage 3 - 2D Vectorization"
  "epic:p4-3d|F9C5F9|Stage 4 - 3D Extrusion"
  "epic:p5-polish|C2E0C6|Stage 5 - Polish and DWG"
  "priority:p0|B60205|Critical / blocker"
  "priority:p1|D93F0B|High"
  "priority:p2|FBCA04|Medium"
  "priority:p3|0E8A16|Low / nice-to-have"
  "status:in-review|1D76DB|PR open and awaiting review"
  "status:blocked|B60205|Blocked by another task"
)
for entry in "${LABELS[@]}"; do
  IFS='|' read -r name color desc <<<"$entry"
  gh label create "$name" --repo "$REPO" --color "$color" --description "$desc" 2>/dev/null || true
done

# ---------------------------------------------------------------------------
# 2. Milestones (one per stage)
# ---------------------------------------------------------------------------
echo "--> Creating milestones"
declare -a STAGES=(
  "Stage 0: Bootstrap|Stage 0 - Bootstrap and Tooling. Repo skeleton, Docker, lint, CI. (US-001 to US-004)|2026-08-31"
  "Stage 1: MVP Skeleton|Stage 1 - MVP Skeleton. Upload, queue, job tracking. (US-005 to US-011)|2026-09-30"
  "Stage 2: PDF Parsing|Stage 2 - PDF Parsing and Preprocessing. Extract and preview page images. (US-012 to US-015)|2026-10-31"
  "Stage 3: 2D Vectorization|Stage 3 - 2D Vectorization. PDF to DXF (core value). (US-016 to US-020)|2026-11-30"
  "Stage 4: 3D Extrusion|Stage 4 - 3D Extrusion. Walls to 3D model. (US-021 to US-024)|2026-12-31"
  "Stage 5: Polish & DWG|Stage 5 - Polish and DWG Export. Production-ready. (US-025 to US-028)|2027-01-31"
)
declare -A MS_NUMBERS
for entry in "${STAGES[@]}"; do
  IFS='|' read -r title desc due <<<"$entry"
  existing=$(gh api "repos/$REPO/milestones?state=open" --jq ".[] | select(.title==\"$title\") | .number" 2>/dev/null || true)
  if [ -z "$existing" ]; then
    num=$(gh api -X POST "repos/$REPO/milestones" \
        -f "title=$title" -f "description=$desc" -f "due_on=${due}T00:00:00Z" \
        --jq '.number')
  else
    num="$existing"
  fi
  MS_NUMBERS["$title"]="$num"
  echo "    milestone $title -> #$num"
done

# ---------------------------------------------------------------------------
# 3. GitHub Project (idempotent)
# ---------------------------------------------------------------------------
echo "--> Creating GitHub Project"
project_id=$(gh project list --owner "$OWNER" --format json --jq ".projects[] | select(.title==\"$PROJECT_TITLE\") | .id" 2>/dev/null || true)
if [ -z "$project_id" ]; then
  project_id=$(gh project create --title "$PROJECT_TITLE" --owner "$OWNER" --format json --jq '.id')
  echo "    created project id=$project_id"
else
  echo "    project already exists id=$project_id"
fi

# ---------------------------------------------------------------------------
# 4. Parent tracking issue
# ---------------------------------------------------------------------------
echo "--> Creating parent tracking issue"
gh issue create --repo "$REPO" \
  --title "AI File Converter - PDF to DWG (project root)" \
  --label "area:docs,type:feature" \
  --body "Tracks the full build-out defined in [README.md](../../README.md) and [TODO.md](../../TODO.md). See **Milestones** for stage-level breakdown, the **AI File Converter** project board for status, and individual issues ([US-001]...[US-028]) for user stories.

## Stage progress
- [ ] Stage 0: Bootstrap (US-001 -> US-004)
- [ ] Stage 1: MVP Skeleton (US-005 -> US-011)
- [ ] Stage 2: PDF Parsing (US-012 -> US-015)
- [ ] Stage 3: 2D Vectorization (US-016 -> US-020)
- [ ] Stage 4: 3D Extrusion (US-021 -> US-024)
- [ ] Stage 5: Polish & DWG (US-025 -> US-028)

## Automation
- Every push and PR runs \`.github/workflows/ci.yml\`
- Every issue/PR activity auto-moves the linked card on the project board via \`.github/workflows/project-sync.yml\`
" 2>/dev/null || true

echo "==> Done. Project: https://github.com/users/$OWNER/projects"
