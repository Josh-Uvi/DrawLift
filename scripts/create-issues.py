#!/usr/bin/env python3
"""Bulk-create one GitHub issue per user story from stories.json."""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = os.environ.get("REPO", "Josh-Uvi/DrawLift")
HERE = Path(__file__).parent


def gh(*args, check=True, capture=True):
    return subprocess.run(["gh", *args], capture_output=capture, text=True, check=check)


def find_existing_issue(title):
    try:
        r = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                REPO,
                "--state",
                "all",
                "--search",
                f'"{title}" in:title',
                "--limit",
                "5",
                "--json",
                "number,title",
            ],
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    if r.returncode != 0 or not r.stdout:
        return None
    for m in json.loads(r.stdout):
        if m["title"] == title:
            return m["number"]
    return None


def get_milestone_numbers():
    r = subprocess.run(
        ["gh", "api", f"repos/{REPO}/milestones?state=open&per_page=100"],
        capture_output=True,
        text=True,
        check=True,
    )
    return {m["title"]: m["number"] for m in json.loads(r.stdout)}


def render_body(s):
    parts = [
        "## Context",
        s["title"],
        "",
        f"**Priority:** {s['priority']}",
        f"**Stage / Milestone:** {s['stage']}",
        f"**Labels:** `{s['labels']}`",
        "",
        "## Acceptance Criteria",
    ]
    parts += [f"- [ ] {a}" for a in s["ac"]]
    parts += ["", "## Tasks"]
    parts += [f"- [ ] {t}" for t in s["tasks"]]
    parts += [
        "",
        "## Definition of Done",
        "- [ ] All acceptance criteria checked",
        "- [ ] All linked tasks (T-XXX) completed",
        "- [ ] Lint passes (`ruff check` / `eslint`)",
        "- [ ] Unit tests exist and pass",
        "- [ ] PR merged to `main` (e.g. `Closes #<this-number>`)",
        "- [ ] Card moved to **Done** on the AI File Converter project board",
    ]
    return "\n".join(parts) + "\n"


def main():
    stories = json.loads((HERE / "stories.json").read_text())
    print(f"==> Loaded {len(stories)} stories from stories.json")

    milestones = get_milestone_numbers()
    print(f"    loaded {len(milestones)} milestones")

    ok = skip = fail = 0
    for s in stories:
        full = f"[{s['id']}] {s['title']}"
        existing = find_existing_issue(full)
        if existing:
            print(f"  exists  {full} -> #{existing}")
            skip += 1
            continue

        body = render_body(s)
        try:
            r = subprocess.run(
                [
                    "gh",
                    "issue",
                    "create",
                    "--repo",
                    REPO,
                    "--title",
                    full,
                    "--body",
                    body,
                    "--label",
                    s["labels"],
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            num = int(r.stdout.strip().rsplit("/", 1)[-1])
        except subprocess.CalledProcessError as e:
            print(f"  FAILED  {full}: {e.stderr or e}", file=sys.stderr)
            fail += 1
            continue

        if s["stage"] in milestones:
            subprocess.run(
                [
                    "gh",
                    "issue",
                    "edit",
                    str(num),
                    "--repo",
                    REPO,
                    "--milestone",
                    s["stage"],
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        print(f"  created {full} -> #{num}")
        ok += 1

    print(f"==> Done. created={ok} skipped={skip} failed={fail} total={len(stories)}")


if __name__ == "__main__":
    main()
