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
        "200",
        "--json",
        "number",
    ],
    capture_output=True,
    text=True,
    check=True,
)
issues = json.loads(r.stdout)
print(f"Found {len(issues)} issues", flush=True)


def existing_item_numbers():
    """Return issue/PR numbers already on the project board."""
    try:
        r = subprocess.run(
            [
                "gh",
                "project",
                "item-list",
                "1",
                "--owner",
                "Josh-Uvi",
                "--format",
                "json",
                "--limit",
                "300",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        items = json.loads(r.stdout).get("items", [])
        numbers = set()
        for item in items:
            content = item.get("content") or {}
            if content.get("number") is not None:
                numbers.add(content["number"])
        return numbers
    except Exception as e:
        print(f"  ! could not list existing project items: {e}", file=sys.stderr)
        return set()


already = existing_item_numbers()
print(f"Project board already has {len(already)} items", flush=True)

ok = fail = skip = 0
for iss in issues:
    n = iss["number"]
    if n in already:
        skip += 1
        continue
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

print(f"added={ok} skipped={skip} failed={fail}", flush=True)
