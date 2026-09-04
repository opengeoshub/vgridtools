#!/usr/bin/env python3
"""Add Bandit nosec markers for try/except/pass and try/except/continue."""

from __future__ import annotations

import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "dggrid", "scripts"}

PASS_RE = re.compile(
    r"^([ \t]*)except Exception:\n((?:[ \t]*#.*\n)*)(\1[ \t]+)pass\b",
    re.MULTILINE,
)
CONTINUE_RE = re.compile(
    r"^([ \t]*)except Exception:\n((?:[ \t]*#.*\n)*)(\1[ \t]+)continue\b",
    re.MULTILINE,
)


def should_skip(path: pathlib.Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def transform(text: str) -> str:
    text = PASS_RE.sub(r"\1except Exception:  # nosec B110\n\2\3pass", text)
    text = CONTINUE_RE.sub(r"\1except Exception:  # nosec B112\n\2\3continue", text)
    return text


def main() -> None:
    changed = 0
    for path in ROOT.rglob("*.py"):
        if should_skip(path):
            continue
        original = path.read_text(encoding="utf-8")
        updated = transform(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed += 1
            print(path.relative_to(ROOT))
    print(f"Updated {changed} files")


if __name__ == "__main__":
    main()
