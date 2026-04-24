# Copyright (c) 2026 John Carter. All rights reserved.
"""
Check that all tracked Python and JavaScript source files contain a copyright header.

Usage:
    python scripts/check_copyright.py          # check; exit 1 if any file is missing
    python scripts/check_copyright.py --fix    # add missing headers (uses current year)

Pattern required (first non-empty line or within first 5 lines):
    Copyright (c) <years> John Carter. All rights reserved.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Directories + extensions to check
TARGETS: list[tuple[Path, str]] = [
    (ROOT / "src", "*.py"),
    (ROOT / "infra", "*.py"),
    (ROOT / "tests", "*.py"),
    (ROOT / "scripts", "*.py"),
    (ROOT / "ui" / "src", "*.js"),
    (ROOT / "ui" / "src", "*.jsx"),
]
SINGLE_FILES: list[Path] = [ROOT / "tasks.py"]

COPYRIGHT_RE = re.compile(r"Copyright \(c\) \d{4}", re.IGNORECASE)

COMMENT_PREFIX: dict[str, str] = {
    ".py": "# ",
    ".js": "// ",
    ".jsx": "// ",
}


def _has_copyright(path: Path) -> bool:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return True  # skip binary files
    return any(COPYRIGHT_RE.search(line) for line in lines[:5])


def _add_copyright(path: Path) -> None:
    prefix = COMMENT_PREFIX.get(path.suffix, "# ")
    year = date.today().year
    header = f"{prefix}Copyright (c) {year} John Carter. All rights reserved.\n"
    original = path.read_text(encoding="utf-8")
    path.write_text(header + original, encoding="utf-8")


def _collect_files() -> list[Path]:
    files: list[Path] = []
    for base, pattern in TARGETS:
        if base.exists():
            files.extend(base.rglob(pattern))
    files.extend(p for p in SINGLE_FILES if p.exists())
    # Exclude caches, generated dirs, and empty init files
    return [
        f
        for f in files
        if "__pycache__" not in f.parts
        and "node_modules" not in f.parts
        and ".venv" not in f.parts
        and "cdk.out" not in f.parts
        and f.name != "__init__.py"
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="Add missing headers automatically")
    args = parser.parse_args()

    files = _collect_files()
    missing = [f for f in files if not _has_copyright(f)]

    if not missing:
        print("copyright: all files OK")
        return 0

    if args.fix:
        for f in missing:
            _add_copyright(f)
            print(f"  added header: {f.relative_to(ROOT)}")
        print(f"copyright: added headers to {len(missing)} file(s)")
        return 0

    print(f"copyright: {len(missing)} file(s) missing copyright header:\n")
    for f in missing:
        print(f"  {f.relative_to(ROOT)}")
    print("\nRun `python scripts/check_copyright.py --fix` to add missing headers.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
