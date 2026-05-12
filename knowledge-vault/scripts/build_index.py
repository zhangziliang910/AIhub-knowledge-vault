#!/usr/bin/env python3
"""Build both SQLite and vector indexes."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(script: str, *args: str) -> None:
    subprocess.check_call([sys.executable, str(ROOT / "scripts" / script), *args], cwd=ROOT)


def main() -> None:
    run("db_init.py")
    run("sync_markdown_to_db.py", "--domain", "all")
    run("sync_markdown_to_vector.py", "--domain", "all")


if __name__ == "__main__":
    main()
