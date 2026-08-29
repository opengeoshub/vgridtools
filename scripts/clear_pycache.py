#!/usr/bin/env python3
"""Remove Python caches and all files under the plugin dggrid/ folder."""

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


def clear_dggrid_folder(root: pathlib.Path) -> tuple[int, int]:
    """Delete every file and subdirectory inside ``dggrid/``; keep the folder."""
    folder = root / "dggrid"
    files_removed = 0
    dirs_removed = 0
    if not folder.is_dir():
        return dirs_removed, files_removed

    for path in folder.iterdir():
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
                dirs_removed += 1
            else:
                path.unlink(missing_ok=True)
                files_removed += 1
        except OSError as exc:
            print(f"  could not remove {path}: {exc}", file=sys.stderr)

    return dirs_removed, files_removed


def main() -> int:
    target = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
    if not target.is_dir():
        print(f"Not a directory: {target}", file=sys.stderr)
        return 1

    dirs_removed, files_removed = clear_pycache(target)
    dggrid_dirs, dggrid_files = clear_dggrid_folder(target)
    print(
        f"Cleared Python caches under {target}\n"
        f"  __pycache__ folders: {dirs_removed}\n"
        f"  .pyc/.pyo files: {files_removed}\n"
        f"Cleared dggrid folder ({target / 'dggrid'})\n"
        f"  files: {dggrid_files}\n"
        f"  subfolders: {dggrid_dirs}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
