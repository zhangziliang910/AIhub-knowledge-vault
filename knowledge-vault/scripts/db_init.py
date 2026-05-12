#!/usr/bin/env python3
from __future__ import annotations

from lib.config import VAULT_ROOT
from lib.db import db_path, init_db
from lib.logging_utils import log_run, now_iso


def ensure_dirs() -> None:
    for path in [
        "data/sqlite", "data/vector/ai", "data/vector/web3", "data/exports",
        "logs/ingestion", "logs/indexing", "logs/retrieval", "logs/errors", "logs/runs",
    ]:
        (VAULT_ROOT / path).mkdir(parents=True, exist_ok=True)


def main() -> None:
    start = now_iso()
    ensure_dirs()
    init_db()
    log_run("runs", [f"db_init start={start}", f"db_init database={db_path()}"])
    print(f"SQLite initialized: {db_path()}")


if __name__ == "__main__":
    main()
