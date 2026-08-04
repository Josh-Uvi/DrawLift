#!/usr/bin/env python3
"""Add all repo issues to the AI File Converter project."""

import json
import subprocess
import sys

REPO = "Josh-Uvi/DrawLift"
PROJECT_ID = "PVT_kwHOAmTEus4BeLBh"

r = subprocess.run(
    [
        "gh",
        "issue",
        "list",
        "--repo",
        REPO,
        "--state",
        "all",
        "--limit",
        "40",
        "--json",
        "number",
    ],
    capture_output=True,
    text=True,
    check=True,
)
issues = json.loads(r.stdout)
print(f"Found {len(issues)} issues", flush=True)

ok = fail = 0
for iss in issues:
    n = iss["number"]
    nid = subprocess.run(
        ["gh", "api", f"repos/{REPO}/issues/{n}", "--jq", ".node_id"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    query = (
        f"mutation {{ addProjectV2ItemById("
        f'input: {{projectId: "{PROJECT_ID}", contentId: "{nid}"}}) '
        f"{{ item {{ id }} }} }}"
    )
    r3 = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}"],
        capture_output=True,
        text=True,
    )
    body = r3.stdout or ""
    if r3.returncode == 0 and '"id"' in body and "PVTI_" in body:
        ok += 1
    else:
        fail += 1
        print(
            f"  ! #{n} rc={r3.returncode} out={body[:150]!r} err={r3.stderr[:150]!r}",
            file=sys.stderr,
            flush=True,
        )

print(f"added={ok} failed={fail}", flush=True)
