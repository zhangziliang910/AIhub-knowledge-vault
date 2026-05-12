from __future__ import annotations

from pathlib import Path
from typing import Any


VAULT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = VAULT_ROOT / "configs"


def _coerce(value: str) -> Any:
    value = value.strip().strip('"').strip("'")
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        return value


def _simple_yaml(text: str) -> dict[str, Any]:
    """Small YAML subset parser used when PyYAML is unavailable."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    last_key_at_indent: dict[int, str] = {}

    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if line.startswith("- "):
            item = _coerce(line[2:])
            if isinstance(parent, list):
                parent.append(item)
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            container: Any = [] if key in {"folders", "keywords", "cross_keywords"} else {}
            if isinstance(parent, dict):
                parent[key] = container
            stack.append((indent, container))
            last_key_at_indent[indent] = key
        else:
            if isinstance(parent, dict):
                parent[key] = _coerce(value)
    return root


def load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text)
        return loaded or {}
    except Exception:
        return _simple_yaml(text)


def load_config(name: str) -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / name)


def app_config() -> dict[str, Any]:
    config = load_config("app_config.yaml")
    config.setdefault("knowledge_root", ".")
    config.setdefault("database_path", "data/sqlite/knowledge.db")
    config.setdefault("vector_root", "data/vector")
    config.setdefault("log_root", "logs")
    config.setdefault("default_top_k", 8)
    return config


def resolve_path(config_value: str) -> Path:
    path = Path(config_value)
    if path.is_absolute():
        return path
    return VAULT_ROOT / path
