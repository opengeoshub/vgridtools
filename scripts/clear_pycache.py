#!/usr/bin/env python3
"""Remove __pycache__ directories and .pyc/.pyo files under the plugin root."""

from __future__ import annotations

import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def clear_pycache(root: pathlib.Path) -> tuple[int, int]:
    dirs_removed = 0
    files_removed = 0

    for cache_dir in root.rglob("__pycache__"):
        if not cache_dir.is_dir():
            continue
        shutil.rmtree(cache_dir, ignore_errors=True)
        dirs_removed += 1

    for pattern in ("*.pyc", "*.pyo"):
        for path in root.rglob(pattern):
            if path.is_file():
                path.unlink(missing_ok=True)
                files_removed += 1

    return dirs_removed, files_removed


def main() -> int:
    target = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
    if not target.is_dir():
        print(f"Not a directory: {target}", file=sys.stderr)
        return 1

    dirs_removed, files_removed = clear_pycache(target)
    print(
        f"Cleared Python caches under {target}\n"
        f"  __pycache__ folders: {dirs_removed}\n"
        f"  .pyc/.pyo files: {files_removed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
