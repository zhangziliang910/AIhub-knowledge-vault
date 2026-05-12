#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from lib.db import connect, init_db
from lib.logging_utils import log_error, log_run, now_iso
from lib.markdown_utils import document_from_markdown, markdown_files


def upsert_document(conn, doc: dict, tags: list[str], entities: list[tuple[str, str]]) -> str:
    existing = conn.execute("SELECT * FROM documents WHERE file_path = ?", (doc["file_path"],)).fetchone()
    timestamp = now_iso()
    comparable = ["domain", "title", "doc_type", "credibility_level", "importance_score", "summary"]
    metadata_changed = bool(existing) and any(str(existing[key]) != str(doc[key]) for key in comparable)
    if existing and existing["content_hash"] == doc["content_hash"] and not metadata_changed:
        return "unchanged"

    if existing:
        doc["updated_at"] = timestamp
        conn.execute(
            """
            UPDATE documents SET
              domain=:domain,title=:title,source=:source,url=:url,author=:author,
              published_at=:published_at,collected_at=:collected_at,doc_type=:doc_type,
              credibility_level=:credibility_level,importance_score=:importance_score,
              summary=:summary,content_hash=:content_hash,status=:status,updated_at=:updated_at
            WHERE file_path=:file_path
            """,
            doc,
        )
        status = "updated"
    else:
        doc["created_at"] = timestamp
        doc["updated_at"] = timestamp
        conn.execute(
            """
            INSERT OR REPLACE INTO documents (
              id,domain,title,source,url,author,published_at,collected_at,doc_type,
              credibility_level,importance_score,summary,file_path,content_hash,status,
              created_at,updated_at
            ) VALUES (
              :id,:domain,:title,:source,:url,:author,:published_at,:collected_at,:doc_type,
              :credibility_level,:importance_score,:summary,:file_path,:content_hash,:status,
              :created_at,:updated_at
            )
            """,
            doc,
        )
        status = "created"

    conn.execute("DELETE FROM document_tags WHERE document_id = ?", (doc["id"],))
    conn.executemany(
        "INSERT INTO document_tags(document_id, tag) VALUES (?, ?)",
        [(doc["id"], tag) for tag in tags],
    )
    conn.execute("DELETE FROM document_entities WHERE document_id = ?", (doc["id"],))
    conn.executemany(
        "INSERT INTO document_entities(document_id, entity_name, entity_type) VALUES (?, ?, ?)",
        [(doc["id"], name, typ) for name, typ in entities],
    )
    return status


def archive_missing(conn, seen_paths: set[str], domain: str) -> int:
    rows = conn.execute("SELECT id,file_path FROM documents WHERE status = 'active'").fetchall()
    archived = 0
    for row in rows:
        file_domain = Path(row["file_path"]).parts[0] if Path(row["file_path"]).parts else ""
        if domain != "all" and file_domain != domain:
            continue
        if row["file_path"] not in seen_paths:
            conn.execute(
                "UPDATE documents SET status = 'archived', updated_at = ? WHERE id = ?",
                (now_iso(), row["id"]),
            )
            archived += 1
    return archived


def sync(domain: str) -> dict[str, int]:
    init_db()
    stats = {"processed": 0, "created": 0, "updated": 0, "unchanged": 0, "archived": 0, "errors": 0}
    seen_paths: set[str] = set()
    with connect() as conn:
        for path in markdown_files(domain):
            try:
                doc, tags, entities = document_from_markdown(path)
                seen_paths.add(doc["file_path"])
                result = upsert_document(conn, doc, tags, entities)
                stats["processed"] += 1
                stats[result] += 1
            except Exception as exc:
                stats["errors"] += 1
                log_error("sync_markdown_to_db", f"{path}: {exc}")
        stats["archived"] = archive_missing(conn, seen_paths, domain)
        conn.execute(
            "INSERT OR REPLACE INTO sync_state(key,value,updated_at) VALUES(?,?,?)",
            ("markdown_to_db_last_run", str(stats), now_iso()),
        )
        conn.commit()
    log_run("indexing", [f"sync_markdown_to_db {stats}"])
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=["all", "ai", "web3"], default="all")
    args = parser.parse_args()
    stats = sync(args.domain)
    print(stats)


if __name__ == "__main__":
    main()
