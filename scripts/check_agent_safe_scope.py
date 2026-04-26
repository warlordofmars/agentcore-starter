# Copyright (c) 2026 John Carter. All rights reserved.
"""
Mechanical scope-boundary check for `agent-safe` PRs.

Issue #77: when an `agent-safe` PR ships, its diff must stay inside the linked
issue's stated scope. This module is the single source of truth for that check;
both `code-reviewer` (pre-merge) and `.github/workflows/agent-safe-scope.yml`
(CI backstop) call into it.

Verdict levels:
- PASS   — every changed file matches the issue's "Files to touch" section or
           a clean area-label glob.
- WARN   — the issue has neither a "Files to touch" section nor a clean
           area-label mapping; the gate cannot make a confident judgement and
           defers (per issue #77 refinements §"Fail-closed → WARN on missing
           scope info"). Issue-creation-time enforcement should ensure this is
           rare.
- FAIL   — the issue has explicit scope info AND the diff strays outside it.

CLI usage:
    python scripts/check_agent_safe_scope.py --pr 123
        # fetches PR diff + linked issue via `gh`, prints verdict, exits non-zero
        # on FAIL.

    python scripts/check_agent_safe_scope.py --issue-body-file body.md \\
        --issue-labels 'ui,priority:p2,agent-safe' --diff-files-file files.txt
        # offline mode for tests / dry runs.

Gating: the CLI resolves the linked issue's labels and only runs the scope
comparison when the issue carries `agent-safe`. Non-agent-safe PRs see a
no-op PASS so the workflow can run unconditionally on every PR (the
`agent-safe` label lives on the **issue**, not the PR, per CLAUDE.md
taxonomy — gating the workflow itself on PR labels would skip nearly every
real agent-safe PR).

The library functions (`evaluate`, `parse_files_to_touch`,
`area_label_paths`, `check_scope`) do not perform the agent-safe gate
themselves — they assume the caller has already decided the check applies.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Literal

# ── Area-label → path-glob map ────────────────────────────────────────────────
#
# Per issue #77 refinements §"Area-label fallback specifics", only bounded
# areas map cleanly to path globs. Meta-areas (dx, security, compliance,
# marketing, growth, seo, design, ops, reliability, performance,
# observability, ux, a11y) span the codebase and cannot be path-mapped —
# their presence triggers a WARN fall-through, not a FAIL.

BOUNDED_AREA_GLOBS: dict[str, list[str]] = {
    "api": ["src/starter/api/**", "tests/unit/test_api*.py", "tests/unit/test_agents_api.py"],
    "auth": ["src/starter/auth/**", "tests/unit/test_auth_*.py", "tests/e2e/test_auth_*.py"],
    "mcp": ["src/starter/mcp/**", "tests/unit/test_mcp_*.py"],
    "infra": ["infra/**"],
    "ui": ["ui/**"],
    "docs": ["docs/**", "docs-site/**", "README.md", "CHANGELOG.md"],
    "ci": [".github/workflows/**", "scripts/**"],
    "sdk": ["sdk/**"],
}

META_AREAS: set[str] = {
    "dx",
    "security",
    "compliance",
    "marketing",
    "growth",
    "seo",
    "design",
    "ops",
    "reliability",
    "performance",
    "observability",
    "ux",
    "a11y",
}


# Always-allowed paths that are universal artifacts of the PR-creation flow
# itself (release notes, changelog churn, etc.). Including them here keeps
# the gate from raising FAIL on housekeeping that every PR is allowed to do.
UNIVERSAL_ALLOWED: list[str] = [
    "CHANGELOG.md",
]


Level = Literal["PASS", "WARN", "FAIL"]


@dataclass(frozen=True)
class Verdict:
    level: Level
    summary: str
    out_of_scope: tuple[str, ...] = ()
    allowed_globs: tuple[str, ...] = ()
    source: str = ""  # "files-to-touch", "area-labels", or "none"

    def to_dict(self) -> dict[str, object]:
        return {
            "level": self.level,
            "summary": self.summary,
            "out_of_scope": list(self.out_of_scope),
            "allowed_globs": list(self.allowed_globs),
            "source": self.source,
        }


# ── Parser ────────────────────────────────────────────────────────────────────


_FILES_TO_TOUCH_HEADING_RE = re.compile(
    r"^#{2,3}\s+Files to touch\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_NEXT_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
# Accept ` `text` `, ` *text* `, or bare path tokens inside a markdown bullet.
# We only want the actual path tokens — not the "New:" / "Edit:" prose prefix.
_BACKTICK_TOKEN_RE = re.compile(r"`([^`]+)`")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.*)$", re.MULTILINE)


def parse_files_to_touch(body: str) -> list[str] | None:
    """
    Extract the list of allowed paths/globs from an issue body's
    "Files to touch" section.

    Returns:
        - A list of path strings (may be empty) if the heading is present.
        - None if no `## Files to touch` / `### Files to touch` heading is
          found (caller falls back to area-label mapping).
    """
    if not body:
        return None

    heading_match = _FILES_TO_TOUCH_HEADING_RE.search(body)
    if not heading_match:
        return None

    section_start = heading_match.end()

    # Find the next heading of any level after our heading — that bounds the
    # section. If none, the section runs to end-of-body.
    next_match = _NEXT_HEADING_RE.search(body, pos=section_start)
    section_end = next_match.start() if next_match else len(body)
    section = body[section_start:section_end]

    paths: list[str] = []
    for bullet in _BULLET_RE.findall(section):
        # Prefer backtick-quoted tokens (unambiguous path markers).
        tokens = _BACKTICK_TOKEN_RE.findall(bullet)
        if tokens:
            paths.extend(t.strip() for t in tokens if t.strip())
            continue
        # Fall back to the bullet text minus a leading "New:" / "Edit:" /
        # "Modify:" prose prefix. This is best-effort; backticks are the
        # supported convention.
        cleaned = re.sub(
            r"^(New|Edit|Modify|Update|Add):\s*", "", bullet.strip(), flags=re.IGNORECASE
        )
        cleaned = cleaned.strip().rstrip(",.;")
        if not cleaned or cleaned.startswith("`"):
            continue
        # Tokenise the bullet on whitespace + common conjunctions/punctuation
        # so a bullet like `- Edit: src/a.py and src/b.py` produces two paths,
        # not one mashed-together string. Each token is then accepted only if
        # it looks like a path (has a `/`) or matches a known top-level file.
        for raw_token in re.split(r"[\s,]+|\band\b", cleaned):
            token = raw_token.strip().rstrip(",.;")
            if not token:
                continue
            looks_like_path = "/" in token or token in {
                "CLAUDE.md",
                "README.md",
                "CHANGELOG.md",
            }
            if looks_like_path:
                paths.append(token)

    return paths


# ── Area-label fallback ───────────────────────────────────────────────────────


def area_label_paths(labels: list[str]) -> list[str] | None:
    """
    Map area labels on the issue to their path globs.

    The repo uses bare area labels (e.g. `ui`, `api`, `auth`) per CLAUDE.md
    §Backlog labels and milestones — NOT prefixed with `area:`. This function
    accepts both forms (`ui` and `area:ui`) for forward-compatibility, but
    the bare form is canonical.

    Identifying which labels are area labels:
        Anything that matches a key in `BOUNDED_AREA_GLOBS` or `META_AREAS`
        is considered an area label. Standard non-area labels (priority:*,
        size:*, status:*, type labels like `enhancement`, special labels
        like `agent-safe`) are filtered out.

    Returns:
        - A list of globs if every area label maps to a bounded area.
        - None if the issue carries no area labels, or if any area label is a
          meta-area (per the BOUNDED_AREA_GLOBS / META_AREAS partition).
          Meta-area presence forces WARN — they cannot be path-mapped.
    """
    # Strip optional `area:` prefix; the repo uses bare names but accept both.
    candidates = [label.removeprefix("area:") for label in labels]

    # Filter to labels that are recognised as areas (bounded or meta). This
    # naturally drops priority:*, size:*, status:*, agent-safe, enhancement,
    # bug, etc.
    area_labels = [c for c in candidates if c in BOUNDED_AREA_GLOBS or c in META_AREAS]
    if not area_labels:
        return None

    globs: list[str] = []
    for area in area_labels:
        if area in META_AREAS:
            return None
        # area is in BOUNDED_AREA_GLOBS by the filter above.
        globs.extend(BOUNDED_AREA_GLOBS[area])

    return globs


# ── Scope comparator ──────────────────────────────────────────────────────────


def _matches_any(path: str, globs: list[str]) -> bool:
    for glob in globs:
        # fnmatch doesn't natively understand `**`. Translate `**` to `*` for
        # an additive match: a glob `src/starter/api/**` should match
        # `src/starter/api/foo/bar.py`. We achieve that by also matching the
        # glob with `**` collapsed to `*` — fnmatch treats `*` as "anything
        # except /" by default? No — in fnmatch `*` matches anything
        # INCLUDING separators. So `src/starter/api/*` will match
        # `src/starter/api/foo/bar.py`. Use that.
        normalised = glob.replace("**", "*")
        if fnmatch.fnmatch(path, normalised):
            return True
        # Also support directory-prefix matches: a glob like `ui/**` should
        # match `ui` itself if it ever appears.
        if glob.endswith("/**") and (path == glob[:-3] or path.startswith(glob[:-2])):
            return True
    return False


def check_scope(diff_files: list[str], allowed_globs: list[str]) -> list[str]:
    """
    Return the list of files in `diff_files` that do NOT match any of the
    `allowed_globs`. Universal-allowed paths are always considered in-scope.
    """
    effective = list(allowed_globs) + UNIVERSAL_ALLOWED
    return [f for f in diff_files if not _matches_any(f, effective)]


# ── Top-level evaluator ───────────────────────────────────────────────────────


def evaluate(
    issue_body: str | None,
    issue_labels: list[str],
    diff_files: list[str],
) -> Verdict:
    """
    Decide whether the PR's diff stays inside the issue's stated scope.

    Resolution order:
    1. If the issue body has a "Files to touch" section, use it.
    2. Else if the issue has bounded area labels (and no meta-areas), use
       their globs.
    3. Else WARN — the gate cannot make a confident judgement.
    """
    files_to_touch = parse_files_to_touch(issue_body or "")

    if files_to_touch is not None:
        if not files_to_touch:
            # Heading present but empty bullet list — treat as WARN; a section
            # with no entries probably means the author forgot to fill it in.
            return Verdict(
                level="WARN",
                summary=(
                    'Issue body has "Files to touch" heading but no parseable '
                    "path entries. Cannot verify scope."
                ),
                source="files-to-touch",
            )
        out = check_scope(diff_files, files_to_touch)
        if out:
            return Verdict(
                level="FAIL",
                summary=(
                    f"PR diff includes {len(out)} file(s) outside the issue's "
                    '"Files to touch" scope.'
                ),
                out_of_scope=tuple(out),
                allowed_globs=tuple(files_to_touch),
                source="files-to-touch",
            )
        return Verdict(
            level="PASS",
            summary='All changed files match the issue\'s "Files to touch" scope.',
            allowed_globs=tuple(files_to_touch),
            source="files-to-touch",
        )

    area_globs = area_label_paths(issue_labels)
    if area_globs is not None:
        out = check_scope(diff_files, area_globs)
        if out:
            return Verdict(
                level="FAIL",
                summary=(f"PR diff includes {len(out)} file(s) outside the area-label path map."),
                out_of_scope=tuple(out),
                allowed_globs=tuple(area_globs),
                source="area-labels",
            )
        return Verdict(
            level="PASS",
            summary="All changed files match the issue's area-label path map.",
            allowed_globs=tuple(area_globs),
            source="area-labels",
        )

    return Verdict(
        level="WARN",
        summary=(
            'Issue body has no "Files to touch" section and no clean area-label '
            "mapping (either no area labels, or area labels include a meta-area "
            "that cannot be path-mapped). Cannot verify scope mechanically."
        ),
        source="none",
    )


# ── CLI ───────────────────────────────────────────────────────────────────────


def _gh(args: list[str]) -> str:
    """Run `gh <args>` and return stdout. Raises on non-zero exit."""
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _fetch_pr_context(pr: int) -> tuple[str | None, list[str], list[str], int | None]:
    """
    Returns (issue_body, issue_labels, diff_files, issue_number).
    issue_body is None if the PR doesn't link an issue.
    """
    pr_json = _gh(["pr", "view", str(pr), "--json", "body,title"])
    pr_data = json.loads(pr_json)
    pr_text = (pr_data.get("body") or "") + "\n" + (pr_data.get("title") or "")

    # Find the linked issue via Closes/Fixes/Resolves #N (case-insensitive).
    issue_match = re.search(
        r"(?:closes|fixes|resolves)\s+#(\d+)",
        pr_text,
        re.IGNORECASE,
    )
    issue_body: str | None = None
    issue_labels: list[str] = []
    issue_num: int | None = None
    if issue_match:
        issue_num = int(issue_match.group(1))
        issue_json = _gh(["issue", "view", str(issue_num), "--json", "body,labels"])
        issue_data = json.loads(issue_json)
        issue_body = issue_data.get("body") or ""
        issue_labels = [label["name"] for label in issue_data.get("labels", [])]

    diff_text = _gh(["pr", "diff", str(pr), "--name-only"])
    diff_files = [line.strip() for line in diff_text.splitlines() if line.strip()]
    return issue_body, issue_labels, diff_files, issue_num


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pr",
        type=int,
        help="PR number — fetches body, labels, and diff via `gh`.",
    )
    parser.add_argument("--issue-body-file", type=str, help="Offline mode: issue body file.")
    parser.add_argument(
        "--issue-labels",
        type=str,
        default="",
        help="Offline mode: comma-separated labels.",
    )
    parser.add_argument(
        "--diff-files-file",
        type=str,
        help="Offline mode: file with one changed-file path per line.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human text.",
    )
    args = parser.parse_args(argv)

    if args.pr:
        issue_body, issue_labels, diff_files, issue_num = _fetch_pr_context(args.pr)
        context_note = (
            f"PR #{args.pr} (linked issue: #{issue_num})" if issue_num else f"PR #{args.pr}"
        )
    else:
        if not (args.issue_body_file and args.diff_files_file):
            parser.error("provide --pr OR (--issue-body-file AND --diff-files-file)")
        with open(args.issue_body_file, encoding="utf-8") as f:
            issue_body = f.read()
        with open(args.diff_files_file, encoding="utf-8") as f:
            diff_files = [line.strip() for line in f if line.strip()]
        issue_labels = [label.strip() for label in args.issue_labels.split(",") if label.strip()]
        context_note = "(offline mode)"

    # Gate: this check only applies when the linked issue carries `agent-safe`.
    # The label lives on the issue per CLAUDE.md taxonomy; the workflow runs
    # unconditionally on every PR and lets us decide here so we can resolve
    # the linked-issue's labels rather than the PR's.
    if "agent-safe" not in issue_labels:
        if args.json:
            print(
                json.dumps(
                    {
                        "level": "PASS",
                        "summary": "PR's linked issue is not labelled `agent-safe` — scope check skipped.",
                        "out_of_scope": [],
                        "allowed_globs": [],
                        "source": "skip",
                    },
                    indent=2,
                )
            )
        else:
            print(f"agent-safe scope check {context_note}")
            print("  verdict: PASS (skipped)")
            print(
                "  reason : linked issue is not labelled `agent-safe` — scope check does not apply."
            )
        return 0

    verdict = evaluate(issue_body, issue_labels, diff_files)

    if args.json:
        print(json.dumps(verdict.to_dict(), indent=2))
    else:
        print(f"agent-safe scope check {context_note}")
        print(f"  source : {verdict.source or 'n/a'}")
        print(f"  verdict: {verdict.level}")
        print(f"  summary: {verdict.summary}")
        if verdict.allowed_globs:
            print("  allowed scope:")
            for g in verdict.allowed_globs:
                print(f"    - {g}")
        if verdict.out_of_scope:
            print("  out-of-scope files:")
            for f in verdict.out_of_scope:
                print(f"    - {f}")

    return 1 if verdict.level == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
