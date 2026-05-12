#!/usr/bin/env python3
from __future__ import annotations

import argparse

from lib.chunking import chunk_document
from lib.config import VAULT_ROOT
from lib.db import connect, init_db
from lib.embedding import get_embedding_provider
from lib.logging_utils import log_error, log_run, now_iso
from lib.markdown_utils import is_vectorizable
from lib.vector_store import get_vector_store


def document_domains(domain: str) -> list[str]:
    if domain == "all":
        return ["ai", "web3"]
    return [domain]


def fetch_docs(conn, domain: str):
    if domain == "all":
        return conn.execute("SELECT * FROM documents WHERE status = 'active'").fetchall()
    return conn.execute(
        "SELECT * FROM documents WHERE status = 'active' AND domain IN (?, 'cross')",
        (domain,),
    ).fetchall()


def existing_chunk_ids(conn, document_id: str) -> set[str]:
    rows = conn.execute("SELECT id FROM chunks WHERE document_id = ? AND embedding_status = 'done'", (document_id,)).fetchall()
    return {row["id"] for row in rows}


def sync(domain: str, rebuild: bool = False) -> dict[str, int]:
    init_db()
    provider = get_embedding_provider()
    stats = {
        "documents": 0,
        "skipped": 0,
        "chunks_added": 0,
        "embedding_success": 0,
        "embedding_failed": 0,
        "errors": 0,
    }
    with connect() as conn:
        if rebuild:
            for store_domain in document_domains(domain):
                get_vector_store(store_domain).reset()
            if domain == "all":
                conn.execute("DELETE FROM chunks")
            else:
                conn.execute("DELETE FROM chunks WHERE domain IN (?, 'cross')", (domain,))
            conn.commit()

        docs = fetch_docs(conn, domain)
        for doc in docs:
            if not is_vectorizable(doc["file_path"]):
                continue
            stats["documents"] += 1
            path = VAULT_ROOT / doc["file_path"]
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            chunks = chunk_document(doc["id"], doc["domain"], doc["file_path"], text)
            new_ids = {chunk.id for chunk in chunks}
            if not rebuild and new_ids and new_ids == existing_chunk_ids(conn, doc["id"]):
                stats["skipped"] += 1
                continue

            conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc["id"],))
            target_domains = ["ai", "web3"] if doc["domain"] == "cross" else [doc["domain"]]
            for store_domain in target_domains:
                get_vector_store(store_domain).delete_document(doc["id"])

            tags = [r["tag"] for r in conn.execute("SELECT tag FROM document_tags WHERE document_id = ?", (doc["id"],))]
            entities = [r["entity_name"] for r in conn.execute("SELECT entity_name FROM document_entities WHERE document_id = ?", (doc["id"],))]
            for chunk in chunks:
                now = now_iso()
                try:
                    embedding = provider.embed_text(chunk.chunk_text)
                    conn.execute(
                        """
                        INSERT INTO chunks(
                          id,document_id,domain,chunk_index,chunk_text,file_path,heading,
                          token_count,embedding_status,created_at,updated_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            chunk.id, chunk.document_id, chunk.domain, chunk.chunk_index,
                            chunk.chunk_text, chunk.file_path, chunk.heading,
                            chunk.token_count, "done", now, now,
                        ),
                    )
                    metadata = {
                        "chunk_id": chunk.id,
                        "document_id": doc["id"],
                        "domain": doc["domain"],
                        "title": doc["title"],
                        "source": doc["source"],
                        "url": doc["url"],
                        "file_path": doc["file_path"],
                        "published_at": doc["published_at"],
                        "doc_type": doc["doc_type"],
                        "credibility_level": doc["credibility_level"],
                        "importance_score": doc["importance_score"],
                        "tags": tags,
                        "entities": entities,
                    }
                    row = {"id": chunk.id, "text": chunk.chunk_text, "embedding": embedding, "metadata": metadata}
                    for store_domain in target_domains:
                        get_vector_store(store_domain).upsert([row])
                    stats["chunks_added"] += 1
                    stats["embedding_success"] += 1
                except Exception as exc:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO chunks(
                          id,document_id,domain,chunk_index,chunk_text,file_path,heading,
                          token_count,embedding_status,created_at,updated_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            chunk.id, chunk.document_id, chunk.domain, chunk.chunk_index,
                            chunk.chunk_text, chunk.file_path, chunk.heading,
                            chunk.token_count, "failed", now, now,
                        ),
                    )
                    stats["embedding_failed"] += 1
                    log_error("sync_markdown_to_vector", f"{chunk.id}: {exc}")
            conn.commit()

        conn.execute(
            "INSERT OR REPLACE INTO sync_state(key,value,updated_at) VALUES(?,?,?)",
            ("markdown_to_vector_last_run", str(stats), now_iso()),
        )
        conn.commit()
    log_run("indexing", [f"sync_markdown_to_vector rebuild={rebuild} {stats}"])
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=["all", "ai", "web3"], default="all")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    stats = sync(args.domain, args.rebuild)
    print(stats)


if __name__ == "__main__":
    main()
