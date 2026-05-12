from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from .config import VAULT_ROOT
from .logging_utils import now_iso


SEARCH_FOLDERS = {"processed", "daily", "weekly", "projects", "concepts"}
OPTIONAL_SEARCH_FOLDERS = {"index"}


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    leading = len(text) - len(text.lstrip())
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return {}, text
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", stripped, re.S)
    if not match:
        return {}, text
    meta: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        raw = raw.strip()
        try:
            value = json.loads(raw)
        except Exception:
            value = raw.strip('"').strip("'")
        meta[key] = value
    return meta, stripped[match.end():]


def first_heading(text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.M)
    return match.group(1).strip() if match else fallback


def summarize(text: str, max_chars: int = 420) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean if len(clean) <= max_chars else clean[:max_chars].rstrip() + "..."


def infer_domain(path: Path, meta: dict[str, Any]) -> str:
    domain = str(meta.get("domain", "")).lower()
    if domain in {"ai", "web3", "cross"}:
        return domain
    parts = {p.lower() for p in path.parts}
    if "ai" in parts:
        return "ai"
    if "web3" in parts:
        return "web3"
    return "cross"


def infer_doc_type(path: Path, meta: dict[str, Any]) -> str:
    raw_type = str(meta.get("doc_type") or meta.get("type") or "").lower()
    mapping = {"product_update": "product", "research": "paper", "business": "investment"}
    if raw_type:
        return mapping.get(raw_type, raw_type)
    if path.name == "index.md":
        return "index"
    folder = path.parent.name.lower()
    return {
        "projects": "project",
        "concepts": "concept",
        "weekly": "weekly",
        "daily": "daily",
        "processed": "processed",
        "raw": "raw",
    }.get(folder, "news")


def normalize_importance(value: Any) -> int:
    try:
        score = int(value)
    except Exception:
        return 3
    if score > 5:
        return max(1, min(5, round(score / 2)))
    return max(1, min(5, score))


def extract_list(meta: dict[str, Any], key: str) -> list[str]:
    value = meta.get(key, [])
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [v.strip() for v in re.split(r"[,，]", value) if v.strip()]
    return []


def extract_entities_from_text(text: str) -> list[tuple[str, str]]:
    known = {
        "OpenAI": "company",
        "Anthropic": "company",
        "Ethereum": "protocol",
        "Solana": "protocol",
        "Bitcoin": "protocol",
        "Claude": "model",
        "ChatGPT": "model",
        "RWA": "concept",
        "DeFi": "concept",
    }
    found = []
    lower = text.lower()
    for name, typ in known.items():
        if name.lower() in lower:
            found.append((name, typ))
    return found


def markdown_files(domain: str = "all") -> list[Path]:
    roots = ["ai", "web3"] if domain == "all" else [domain]
    files: list[Path] = []
    for root in roots:
        base = VAULT_ROOT / root
        if base.exists():
            files.extend(base.rglob("*.md"))
    return sorted(files)


def document_from_markdown(path: Path) -> tuple[dict[str, Any], list[str], list[tuple[str, str]]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    meta, body = parse_frontmatter(text)
    rel = path.relative_to(VAULT_ROOT).as_posix()
    title = str(meta.get("title") or first_heading(body, path.stem))
    doc_id = str(meta.get("id") or stable_id(rel))
    tags = extract_list(meta, "tags")
    entities = [(name, "concept") for name in extract_list(meta, "entities")]
    if not entities:
        entities = extract_entities_from_text(text)
    doc = {
        "id": doc_id,
        "domain": infer_domain(path, meta),
        "title": title,
        "source": str(meta.get("source", "")),
        "url": str(meta.get("url", "")),
        "author": str(meta.get("author", "")),
        "published_at": str(meta.get("published_at", "")),
        "collected_at": str(meta.get("collected_at", "")) or now_iso(),
        "doc_type": infer_doc_type(path, meta),
        "credibility_level": str(meta.get("credibility_level", "B") or "B"),
        "importance_score": normalize_importance(meta.get("importance_score", 3)),
        "summary": str(meta.get("summary") or summarize(body)),
        "file_path": rel,
        "content_hash": content_hash(text),
        "status": "active",
    }
    return doc, tags, entities


def is_vectorizable(file_path: str, include_raw: bool = False) -> bool:
    parts = Path(file_path).parts
    if not parts:
        return False
    folder = Path(file_path).parent.name
    if Path(file_path).name == "index.md":
        return True
    if folder == "raw":
        return include_raw
    return folder in SEARCH_FOLDERS
