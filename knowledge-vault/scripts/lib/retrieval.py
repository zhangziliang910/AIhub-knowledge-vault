from __future__ import annotations

import datetime as dt
import math
import re
from collections import defaultdict
from typing import Any

from .config import load_config
from .db import connect, init_db
from .embedding import get_embedding_provider
from .vector_store import get_vector_store


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]{2,}", text.lower())


def domains_for_query(domain: str) -> list[str]:
    if domain in {"cross", "unknown", "all"}:
        return ["ai", "web3"]
    return [domain]


def recency_score(published_at: str) -> float:
    if not published_at:
        return 0.4
    try:
        day = dt.date.fromisoformat(published_at[:10])
    except Exception:
        return 0.4
    age = max(0, (dt.date.today() - day).days)
    return max(0.0, 1.0 - min(age, 365) / 365)


def row_metadata(conn, chunk_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT c.id chunk_id,c.document_id,c.domain,c.chunk_text,c.file_path,c.heading,
               d.title,d.source,d.url,d.published_at,d.doc_type,d.credibility_level,d.importance_score
        FROM chunks c JOIN documents d ON c.document_id = d.id
        WHERE c.id = ? AND d.status = 'active'
        """,
        (chunk_id,),
    ).fetchone()
    return dict(row) if row else None


def keyword_search(conn, question: str, domains: list[str], limit: int) -> list[dict[str, Any]]:
    terms = tokenize(question)
    if not terms:
        return []
    domain_placeholders = ",".join("?" for _ in domains)
    rows = conn.execute(
        f"""
        SELECT c.id chunk_id,c.document_id,c.domain,c.chunk_text,c.file_path,c.heading,
               d.title,d.source,d.url,d.published_at,d.doc_type,d.credibility_level,d.importance_score
        FROM chunks c JOIN documents d ON c.document_id = d.id
        WHERE d.status = 'active' AND c.domain IN ({domain_placeholders}, 'cross')
        """,
        domains,
    ).fetchall()
    scored = []
    q = set(terms)
    for row in rows:
        text_terms = set(tokenize(row["chunk_text"] + " " + row["title"]))
        overlap = len(q & text_terms)
        if overlap:
            scored.append({**dict(row), "semantic_score": min(1.0, overlap / max(1, len(q)))})
    return sorted(scored, key=lambda r: r["semantic_score"], reverse=True)[:limit]


def passes_filters(item: dict[str, Any], filters: dict[str, Any]) -> bool:
    if filters.get("credibility_levels") and item.get("credibility_level") not in set(filters["credibility_levels"]):
        return False
    if filters.get("min_importance") and int(item.get("importance_score") or 0) < int(filters["min_importance"]):
        return False
    if filters.get("doc_type"):
        values = filters["doc_type"] if isinstance(filters["doc_type"], list) else [filters["doc_type"]]
        if item.get("doc_type") not in values:
            return False
    if filters.get("start_date") and str(item.get("published_at", ""))[:10] < filters["start_date"]:
        return False
    if filters.get("end_date") and str(item.get("published_at", ""))[:10] > filters["end_date"]:
        return False
    return True


def final_score(item: dict[str, Any], semantic_score: float) -> float:
    config = load_config("retrieval_config.yaml")
    weights = config.get("weights", {})
    credibility = config.get("credibility_weight", {})
    doc_type = config.get("doc_type_weight", {})
    cred = float(credibility.get(item.get("credibility_level"), 0.5))
    importance = min(1.0, float(item.get("importance_score") or 1) / 5)
    fresh = recency_score(str(item.get("published_at") or ""))
    dtype = float(doc_type.get(item.get("doc_type"), 0.7))
    return (
        semantic_score * float(weights.get("semantic_similarity", 0.60))
        + cred * float(weights.get("credibility", 0.15))
        + importance * float(weights.get("importance", 0.15))
        + fresh * float(weights.get("recency", 0.05))
        + dtype * float(weights.get("doc_type", 0.05))
    )


def retrieve(question: str, domain: str = "all", top_k: int | None = None, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    init_db()
    config = load_config("retrieval_config.yaml")
    top_k = int(top_k or config.get("top_k", 8))
    max_per_doc = int(config.get("max_chunks_per_document", 3))
    filters = filters or {}
    domains = domains_for_query(domain)
    provider = get_embedding_provider()
    query_vector = provider.embed_text(question)

    candidates: dict[str, dict[str, Any]] = {}
    with connect() as conn:
        for d in domains:
            vector_filters = {**filters}
            for row in get_vector_store(d).query(query_vector, top_k * 4, vector_filters):
                if float(row["score"]) < 0.08:
                    continue
                chunk_id = row["metadata"]["chunk_id"]
                meta = row_metadata(conn, chunk_id)
                if not meta:
                    continue
                meta["semantic_score"] = max(0.0, float(row["score"]))
                candidates[chunk_id] = meta

        for row in keyword_search(conn, question, domains, top_k * 4):
            chunk_id = row["chunk_id"]
            if chunk_id in candidates:
                candidates[chunk_id]["semantic_score"] = max(candidates[chunk_id]["semantic_score"], row["semantic_score"])
            else:
                candidates[chunk_id] = row

    deduped = []
    per_doc = defaultdict(int)
    for item in sorted(candidates.values(), key=lambda x: final_score(x, x.get("semantic_score", 0)), reverse=True):
        if not passes_filters(item, filters):
            continue
        if per_doc[item["document_id"]] >= max_per_doc:
            continue
        per_doc[item["document_id"]] += 1
        score = final_score(item, item.get("semantic_score", 0))
        deduped.append({
            "chunk_id": item["chunk_id"],
            "document_id": item["document_id"],
            "domain": item["domain"],
            "title": item["title"],
            "source": item["source"],
            "url": item["url"],
            "file_path": item["file_path"],
            "published_at": item["published_at"],
            "doc_type": item["doc_type"],
            "credibility_level": item["credibility_level"],
            "importance_score": item["importance_score"],
            "chunk_text": item["chunk_text"],
            "score": round(score, 4),
        })
        if len(deduped) >= top_k:
            break
    return deduped
