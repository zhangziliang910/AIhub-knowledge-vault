from __future__ import annotations

import datetime as dt
from pathlib import Path

from .config import VAULT_ROOT


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def log_run(module: str, lines: list[str]) -> None:
    folder = VAULT_ROOT / "logs" / module
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{dt.date.today().isoformat()}.log"
    with path.open("a", encoding="utf-8") as f:
        for line in lines:
            f.write(f"{now_iso()} {line}\n")


def log_error(module: str, message: str) -> None:
    folder = VAULT_ROOT / "logs" / "errors"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{dt.date.today().isoformat()}.log"
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{now_iso()} [{module}] {message}\n")
