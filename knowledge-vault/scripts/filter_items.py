#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from difflib import SequenceMatcher
from typing import Any

from lib.config import VAULT_ROOT, load_config
from lib.db import connect, init_db
from lib.logging_utils import log_run, now_iso
from lib.pipeline_utils import read_jsonl, today_str, write_jsonl


DOC_TYPE_KEYWORDS = {
    "paper": ["paper", "arxiv", "论文", "research"],
    "investment": ["funding", "raises", "融资", "ipo", "acquisition", "收购"],
    "policy": ["policy", "regulation", "监管", "法案", "sec", "cftc"],
    "product": ["launch", "release", "发布", "introducing", "上线"],
    "security": ["hack", "exploit", "漏洞", "攻击", "安全"],
    "data": ["data", "report", "数据", "dashboard", "dune", "defillama"],
    "opinion": ["opinion", "观点", "analysis", "分析"],
}

HIGH_SIGNAL = [
    "openai", "anthropic", "agent", "mcp", "rag", "github", "model",
    "ethereum", "solana", "defi", "rwa", "stablecoin", "稳定币", "监管",
    "银行", "金融", "identity", "身份", "数据确权", "知识协作",
]


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def infer_doc_type(text: str) -> str:
    lower = text.lower()
    for doc_type, keywords in DOC_TYPE_KEYWORDS.items():
        if any(k.lower() in lower for k in keywords):
            return doc_type
    return "news"


def score_item(item: dict[str, Any]) -> int:
    text = f"{item.get('title','')} {item.get('excerpt','')}".lower()
    score = {"A": 2, "B": 1, "C": 0, "D": 0}.get(item.get("credibility_level", "B"), 1)
    score += min(2, sum(1 for kw in HIGH_SIGNAL if kw in text))
    if item.get("published_at"):
        score += 1
    return max(1, min(5, score))


def existing_docs() -> list[dict[str, str]]:
    init_db()
    with connect() as conn:
        rows = conn.execute("SELECT title,url,summary FROM documents WHERE status='active'").fetchall()
        return [dict(r) for r in rows]


def is_duplicate(item: dict[str, Any], docs: list[dict[str, str]], title_threshold: float, summary_threshold: float) -> bool:
    url = item.get("url", "")
    title = item.get("title", "")
    excerpt = item.get("excerpt", "")
    for doc in docs:
        if url and doc.get("url") == url:
            return True
        if title and similarity(title, doc.get("title", "")) >= title_threshold:
            return True
        if excerpt and similarity(excerpt[:300], doc.get("summary", "")[:300]) >= summary_threshold:
            return True
    return False


def filter_domain(domain: str, date: str | None = None) -> dict[str, int]:
    config = load_config("ingestion_config.yaml")
    day = date or today_str()
    source_path = VAULT_ROOT / "data" / "collections" / day / f"{domain}.jsonl"
    rows = read_jsonl(source_path)
    docs = existing_docs()
    accepted = []
    rejected = []
    stats = {"collected": len(rows), "duplicates": 0, "accepted": 0, "ignored": 0, "failed": 0}
    for item in rows:
        try:
            duplicate = is_duplicate(
                item,
                docs,
                float(config.get("title_similarity_threshold", 0.82)),
                float(config.get("summary_similarity_threshold", 0.78)),
            )
            item["doc_type"] = infer_doc_type(f"{item.get('title','')} {item.get('excerpt','')}")
            item["importance_score"] = score_item(item)
            item["decision"] = "ingest"
            if duplicate:
                item["decision"] = "duplicate"
                stats["duplicates"] += 1
                rejected.append(item)
            elif item["importance_score"] < int(config.get("min_importance_to_ingest", 2)):
                item["decision"] = "low_value"
                stats["ignored"] += 1
                rejected.append(item)
            else:
                accepted.append(item)
                docs.append({"title": item.get("title", ""), "url": item.get("url", ""), "summary": item.get("excerpt", "")})
                stats["accepted"] += 1
        except Exception:
            stats["failed"] += 1
    write_jsonl(VAULT_ROOT / "data" / "filtered" / day / f"{domain}-accepted.jsonl", accepted)
    write_jsonl(VAULT_ROOT / "data" / "filtered" / day / f"{domain}-rejected.jsonl", rejected)
    log_run("pipeline", [f"filter_items date={day} domain={domain} stats={stats}"])
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=["all", "ai", "web3"], default="all")
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    domains = ["ai", "web3"] if args.domain == "all" else [args.domain]
    total = {}
    for domain in domains:
        total[domain] = filter_domain(domain, args.date)
    print(total)


if __name__ == "__main__":
    main()
