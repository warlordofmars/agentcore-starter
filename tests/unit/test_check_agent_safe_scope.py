# Copyright (c) 2026 John Carter. All rights reserved.
"""
Unit tests for scripts/check_agent_safe_scope.py.

Covers all six matrix cases (a)–(f) from issue #77 refinements
§"Validation test matrix":

(a) No Files-to-touch, area:ui, diff in ui/src/        — PASS
(b) No Files-to-touch, area:dx                          — WARN (meta-area)
(c) Files-to-touch listed, diff inside scope            — PASS
(d) Files-to-touch listed, diff strays outside (PR #76) — FAIL
(e) Multiple area labels — verify mapping precedence
(f) Both heading levels (## and ###)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = ROOT / "scripts" / "check_agent_safe_scope.py"

# scripts/ isn't a package; load the module by file path so tests don't rely
# on PYTHONPATH being set.
_spec = importlib.util.spec_from_file_location("check_agent_safe_scope", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
scope_check = importlib.util.module_from_spec(_spec)
sys.modules["check_agent_safe_scope"] = scope_check
_spec.loader.exec_module(scope_check)


# ── Parser tests ──────────────────────────────────────────────────────────────


def test_parse_files_to_touch_h2_heading():
    body = """## Context

Some context.

## Files to touch

- New: `.claude/skills/foo/SKILL.md`
- Edit: `CLAUDE.md`

## Acceptance criteria

- [ ] thing
"""
    assert scope_check.parse_files_to_touch(body) == [
        ".claude/skills/foo/SKILL.md",
        "CLAUDE.md",
    ]


def test_parse_files_to_touch_h3_heading():
    """Case (f) — both ## and ### heading levels parse."""
    body = """### Files to touch

- New: `.claude/skills/bar/SKILL.md`

### Acceptance criteria
- [ ] thing
"""
    assert scope_check.parse_files_to_touch(body) == [
        ".claude/skills/bar/SKILL.md",
    ]


def test_parse_files_to_touch_missing_returns_none():
    body = "## Context\n\nNothing scoped.\n\n## Acceptance criteria\n- [ ] thing"
    assert scope_check.parse_files_to_touch(body) is None


def test_parse_files_to_touch_empty_body_returns_none():
    assert scope_check.parse_files_to_touch("") is None


def test_parse_files_to_touch_multiple_backticks_in_one_bullet():
    body = """## Files to touch

- Edit: `src/starter/api/foo.py` and `tests/unit/test_foo.py`

## Next
"""
    assert scope_check.parse_files_to_touch(body) == [
        "src/starter/api/foo.py",
        "tests/unit/test_foo.py",
    ]


def test_parse_files_to_touch_bare_path_without_backticks():
    body = """## Files to touch

- New: src/starter/foo.py
- Edit: CLAUDE.md

## Next
"""
    # Bare paths should still be picked up — slashes or known top-level files.
    parsed = scope_check.parse_files_to_touch(body)
    assert parsed is not None
    assert "src/starter/foo.py" in parsed
    assert "CLAUDE.md" in parsed


def test_parse_files_to_touch_bare_paths_multiple_per_bullet():
    """A single bullet containing multiple unquoted paths must yield each
    path separately, not one mashed-together string. Real-world example:
        - Edit: src/a.py and src/b.py
    Without tokenisation this would parse as one phantom path that never
    matches any diff entry, causing false FAILs."""
    body = """## Files to touch

- Edit: src/starter/foo.py and src/starter/bar.py
- New: docs/a.md, docs/b.md

## Next
"""
    parsed = scope_check.parse_files_to_touch(body)
    assert parsed is not None
    assert "src/starter/foo.py" in parsed
    assert "src/starter/bar.py" in parsed
    assert "docs/a.md" in parsed
    assert "docs/b.md" in parsed
    # No mashed-together token should sneak through.
    assert all(" " not in p for p in parsed)


def test_parse_files_to_touch_skips_descriptive_bullets():
    body = """## Files to touch

- Just some prose without paths
- `.claude/skills/qux/SKILL.md`

## Next
"""
    parsed = scope_check.parse_files_to_touch(body)
    assert parsed == [".claude/skills/qux/SKILL.md"]


def test_parse_files_to_touch_heading_at_end_of_body():
    body = "## Files to touch\n\n- `foo.py`\n"
    assert scope_check.parse_files_to_touch(body) == ["foo.py"]


def test_parse_files_to_touch_empty_section():
    body = "## Files to touch\n\n## Next\n"
    # Heading present but no bullets → empty list (NOT None).
    assert scope_check.parse_files_to_touch(body) == []


# ── Area-label fallback tests ─────────────────────────────────────────────────


def test_area_label_paths_bounded_area_ui_bare_label():
    """Repo uses bare area labels (no `area:` prefix) per CLAUDE.md.
    Real-world labels look like `ui`, `api`, `auth` — not `area:ui`."""
    globs = scope_check.area_label_paths(["ui", "priority:p2", "size:s"])
    assert globs is not None
    assert any(g.startswith("ui/") for g in globs)


def test_area_label_paths_bounded_area_prefixed_form_also_accepted():
    """Forward-compatibility: `area:ui` form works too."""
    globs = scope_check.area_label_paths(["area:ui", "priority:p2"])
    assert globs is not None
    assert any(g.startswith("ui/") for g in globs)


def test_area_label_paths_meta_area_returns_none():
    """Case (b) — `dx` is a meta-area, no clean path map → None → WARN."""
    assert scope_check.area_label_paths(["dx", "priority:p2"]) is None


def test_area_label_paths_no_area_labels_returns_none():
    assert scope_check.area_label_paths(["priority:p1", "size:m"]) is None


def test_area_label_paths_filters_out_non_area_labels():
    """Standard non-area labels (status, type, agent-safe) are filtered out
    before the area check runs. Real issues carry many such labels."""
    globs = scope_check.area_label_paths(
        [
            "ui",
            "agent-safe",
            "enhancement",
            "documentation",
            "status:ready",
            "priority:p2",
            "size:s",
        ]
    )
    assert globs is not None
    assert any(g.startswith("ui/") for g in globs)


def test_area_label_paths_multiple_bounded_areas_combine():
    """Case (e) — multiple area labels combine into a union of globs."""
    globs = scope_check.area_label_paths(["api", "auth"])
    assert globs is not None
    assert any(g.startswith("src/starter/api/") for g in globs)
    assert any(g.startswith("src/starter/auth/") for g in globs)


def test_area_label_paths_meta_in_mix_disables_fallback():
    """If any area label is a meta-area, fall through to WARN — partial
    bounded-area coverage isn't reliable enough."""
    assert scope_check.area_label_paths(["ui", "dx"]) is None


def test_area_label_paths_unrecognised_label_is_ignored():
    """A label that's neither in BOUNDED_AREA_GLOBS nor META_AREAS (e.g.
    a custom workflow label) is not treated as an area label at all."""
    assert scope_check.area_label_paths(["custom-label", "priority:p2"]) is None


# ── check_scope tests ─────────────────────────────────────────────────────────


def test_check_scope_all_in_scope():
    out = scope_check.check_scope(
        diff_files=["ui/src/foo.jsx", "ui/src/bar.jsx"],
        allowed_globs=["ui/**"],
    )
    assert out == []


def test_check_scope_some_out_of_scope():
    out = scope_check.check_scope(
        diff_files=["ui/src/foo.jsx", "src/starter/api/bad.py"],
        allowed_globs=["ui/**"],
    )
    assert out == ["src/starter/api/bad.py"]


def test_check_scope_universal_allowed_paths_pass():
    """CHANGELOG.md is universal-allowed regardless of scope."""
    out = scope_check.check_scope(
        diff_files=["ui/src/foo.jsx", "CHANGELOG.md"],
        allowed_globs=["ui/**"],
    )
    assert out == []


def test_check_scope_glob_with_double_star():
    out = scope_check.check_scope(
        diff_files=["src/starter/api/deep/nested/file.py"],
        allowed_globs=["src/starter/api/**"],
    )
    assert out == []


def test_check_scope_exact_path_match():
    out = scope_check.check_scope(
        diff_files=[".claude/skills/foo/SKILL.md"],
        allowed_globs=[".claude/skills/foo/SKILL.md"],
    )
    assert out == []


# ── End-to-end evaluator tests (the six matrix cases) ────────────────────────


def test_case_a_no_files_to_touch_area_ui_diff_in_ui_passes():
    """(a) No Files-to-touch, area `ui`, diff in ui/src/ — PASS."""
    body = "## Context\n\nNothing.\n"
    labels = ["ui", "agent-safe"]  # bare label form, as used in the repo
    diff = ["ui/src/components/Foo.jsx"]
    v = scope_check.evaluate(body, labels, diff)
    assert v.level == "PASS"
    assert v.source == "area-labels"


def test_case_b_no_files_to_touch_area_dx_warns():
    """(b) No Files-to-touch, area `dx` (meta) — WARN."""
    body = "## Context\n\nNothing.\n"
    labels = ["dx", "agent-safe"]  # bare label form
    diff = ["scripts/foo.py"]
    v = scope_check.evaluate(body, labels, diff)
    assert v.level == "WARN"
    assert v.source == "none"


def test_case_c_files_to_touch_in_scope_passes():
    """(c) Files-to-touch listed, diff inside scope — PASS."""
    body = """## Files to touch

- New: `.claude/skills/foo/SKILL.md`

## Acceptance criteria
"""
    labels = ["agent-safe"]
    diff = [".claude/skills/foo/SKILL.md"]
    v = scope_check.evaluate(body, labels, diff)
    assert v.level == "PASS"
    assert v.source == "files-to-touch"


def test_case_d_files_to_touch_strays_fails_pr76_scenario():
    """(d) Files-to-touch listed, diff strays outside (the PR #76 case) — FAIL."""
    body = """## Files to touch

- New: `.claude/skills/react-component/SKILL.md`
- New: `.claude/skills/react-component/example.jsx`

## Acceptance criteria
"""
    labels = ["agent-safe", "ui"]
    diff = [
        ".claude/skills/react-component/SKILL.md",
        ".claude/skills/react-component/example.jsx",
        ".claude/agents/code-reviewer.md",  # ride-along
        "CLAUDE.md",  # ride-along
    ]
    v = scope_check.evaluate(body, labels, diff)
    assert v.level == "FAIL"
    assert v.source == "files-to-touch"
    assert ".claude/agents/code-reviewer.md" in v.out_of_scope
    assert "CLAUDE.md" in v.out_of_scope
    assert ".claude/skills/react-component/SKILL.md" not in v.out_of_scope


def test_case_e_multiple_area_labels_mapping_precedence():
    """(e) Multiple area labels — globs union, files matching either pass."""
    body = "## Context\n\nNo files-to-touch section.\n"
    labels = ["api", "auth", "agent-safe"]
    diff = [
        "src/starter/api/foo.py",
        "src/starter/auth/oauth.py",
    ]
    v = scope_check.evaluate(body, labels, diff)
    assert v.level == "PASS"
    assert v.source == "area-labels"


def test_case_e_multiple_areas_with_out_of_scope_file_fails():
    body = "## Context\n\nNo files-to-touch section.\n"
    labels = ["api", "auth", "agent-safe"]
    diff = [
        "src/starter/api/foo.py",
        "ui/src/components/Foo.jsx",  # out of scope for api+auth
    ]
    v = scope_check.evaluate(body, labels, diff)
    assert v.level == "FAIL"
    assert "ui/src/components/Foo.jsx" in v.out_of_scope


def test_case_f_h2_heading_in_evaluator():
    """(f) H2 heading → parsed correctly by the full evaluator."""
    body = """## Files to touch

- `src/starter/foo.py`

## More
"""
    v = scope_check.evaluate(body, ["agent-safe"], ["src/starter/foo.py"])
    assert v.level == "PASS"


def test_case_f_h3_heading_in_evaluator():
    """(f) H3 heading → parsed correctly by the full evaluator."""
    body = """### Files to touch

- `src/starter/foo.py`

### More
"""
    v = scope_check.evaluate(body, ["agent-safe"], ["src/starter/foo.py"])
    assert v.level == "PASS"


# ── Additional safety-net tests ───────────────────────────────────────────────


def test_evaluate_warns_when_no_scope_info_anywhere():
    body = "## Context\n\nNo info.\n"
    v = scope_check.evaluate(body, ["priority:p2"], ["src/starter/foo.py"])
    assert v.level == "WARN"
    assert v.source == "none"


def test_evaluate_warns_when_files_to_touch_section_is_empty():
    body = "## Files to touch\n\n## Next\n"
    v = scope_check.evaluate(body, ["agent-safe"], ["foo.py"])
    assert v.level == "WARN"
    assert v.source == "files-to-touch"


def test_evaluate_handles_none_body():
    """A PR linked to no issue → body=None → WARN."""
    v = scope_check.evaluate(None, [], ["foo.py"])
    assert v.level == "WARN"


def test_verdict_to_dict_serialises_cleanly():
    body = """## Files to touch

- `foo.py`
"""
    v = scope_check.evaluate(body, [], ["foo.py", "bar.py"])
    d = v.to_dict()
    assert d["level"] == "FAIL"
    assert d["out_of_scope"] == ["bar.py"]
    assert d["source"] == "files-to-touch"
    assert d["allowed_globs"] == ["foo.py"]


def test_universal_allowed_changelog_passes_in_files_to_touch_mode():
    body = """## Files to touch

- `src/starter/foo.py`
"""
    v = scope_check.evaluate(body, [], ["src/starter/foo.py", "CHANGELOG.md"])
    assert v.level == "PASS"
