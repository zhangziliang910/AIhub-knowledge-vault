from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .config import VAULT_ROOT, app_config, resolve_path


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (
        math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1.0
    )


class LocalJsonVectorStore:
    """Tiny local vector database fallback.

    It persists one JSON file per domain collection. This is deliberately simple
    and dependency-free, while exposing operations similar to Chroma/LanceDB.
    """

    def __init__(self, domain: str) -> None:
        config = app_config()
        root = resolve_path(config["vector_root"])
        self.domain = domain
        self.collection_name = f"{domain}_knowledge"
        self.folder = root / domain
        self.path = self.folder / f"{self.collection_name}.json"
        self.folder.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save({})

    def _load(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def reset(self) -> None:
        self._save({})

    def delete_document(self, document_id: str) -> int:
        data = self._load()
        before = len(data)
        data = {k: v for k, v in data.items() if v.get("metadata", {}).get("document_id") != document_id}
        self._save(data)
        return before - len(data)

    def upsert(self, rows: list[dict[str, Any]]) -> None:
        data = self._load()
        for row in rows:
            data[row["id"]] = row
        self._save(data)

    def query(
        self,
        query_embedding: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        data = self._load()
        results = []
        for row in data.values():
            meta = row.get("metadata", {})
            if not self._match_filters(meta, filters):
                continue
            score = cosine(query_embedding, row.get("embedding", []))
            results.append({**row, "score": score})
        return sorted(results, key=lambda r: r["score"], reverse=True)[:top_k]

    @staticmethod
    def _match_filters(meta: dict[str, Any], filters: dict[str, Any]) -> bool:
        for key, value in filters.items():
            if value in (None, "", []):
                continue
            if key == "min_importance":
                if int(meta.get("importance_score") or 0) < int(value):
                    return False
            elif key == "credibility_levels":
                if meta.get("credibility_level") not in set(value):
                    return False
            elif key == "doc_type":
                values = value if isinstance(value, list) else [value]
                if meta.get("doc_type") not in values:
                    return False
            elif key == "domain":
                if meta.get("domain") != value:
                    return False
            else:
                if meta.get(key) != value:
                    return False
        return True

    def count(self) -> int:
        return len(self._load())


def get_vector_store(domain: str) -> LocalJsonVectorStore:
    return LocalJsonVectorStore(domain)
