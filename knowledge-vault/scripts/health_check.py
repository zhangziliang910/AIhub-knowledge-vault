#!/usr/bin/env python3
from __future__ import annotations

from lib.config import VAULT_ROOT
from lib.config import load_config
from lib.db import connect, db_path, init_db
from lib.markdown_utils import markdown_files
from lib.vector_store import get_vector_store


REQUIRED_TABLES = {"documents", "document_tags", "document_entities", "chunks", "sources", "questions"}


def table_exists(conn, name: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row is not None


def domain_stats(conn, domain: str) -> dict:
    markdown_count = len(markdown_files(domain))
    documents = conn.execute("SELECT COUNT(*) c FROM documents WHERE status='active' AND domain IN (?, 'cross')", (domain,)).fetchone()["c"]
    chunks = conn.execute("SELECT COUNT(*) c FROM chunks WHERE domain IN (?, 'cross')", (domain,)).fetchone()["c"]
    done = conn.execute("SELECT COUNT(*) c FROM chunks WHERE domain IN (?, 'cross') AND embedding_status='done'", (domain,)).fetchone()["c"]
    failed = conn.execute("SELECT COUNT(*) c FROM chunks WHERE domain IN (?, 'cross') AND embedding_status='failed'", (domain,)).fetchone()["c"]
    vectorized = get_vector_store(domain).count()
    return {
        "markdown files": markdown_count,
        "documents": documents,
        "chunks": chunks,
        "vectorized chunks": vectorized or done,
        "failed chunks": failed,
    }


def main() -> None:
    init_db()
    print("Knowledge Vault Health Check\n")
    print("[OK] knowledge-vault directory exists" if VAULT_ROOT.exists() else "[FAIL] knowledge-vault directory missing")
    print("[OK] SQLite database exists" if db_path().exists() else "[FAIL] SQLite database missing")
    with connect() as conn:
        for table in sorted(REQUIRED_TABLES):
            print(f"[OK] {table} table exists" if table_exists(conn, table) else f"[FAIL] {table} table missing")
    print("[OK] vector store available")
    sources_path = VAULT_ROOT / "configs" / "sources.yaml"
    print("[OK] sources.yaml exists" if sources_path.exists() else "[FAIL] sources.yaml missing")
    if sources_path.exists():
        sources = load_config("sources.yaml").get("sources", {})
        enabled = 0
        for groups in sources.values():
            for items in groups.values():
                enabled += sum(1 for item in items if item.get("enabled", True))
        print(f"[OK] enabled sources: {enabled}")
        for domain in ["ai", "web3"]:
            stats = domain_stats(conn, domain)
            print(f"\n{domain.upper()}:")
            for key, value in stats.items():
                print(f"- {key}: {value}")
        row = conn.execute("SELECT key,value,updated_at FROM sync_state ORDER BY updated_at DESC LIMIT 1").fetchone()
        print("\nRecent sync:")
        print(f"- {row['key']}: {row['updated_at']} {row['value']}" if row else "- none")
        print("\nPipeline files:")
        for label, path in {
            "latest collection": VAULT_ROOT / "data" / "collections",
            "latest daily html": VAULT_ROOT / "reports" / "daily",
            "latest run report": VAULT_ROOT / "logs" / "runs",
            "ai expert_profile": VAULT_ROOT / "ai" / "expert_profile.md",
            "ai trend_memory": VAULT_ROOT / "ai" / "trend_memory.md",
            "web3 expert_profile": VAULT_ROOT / "web3" / "expert_profile.md",
            "web3 trend_memory": VAULT_ROOT / "web3" / "trend_memory.md",
        }.items():
            if path.is_dir():
                files = sorted([p for p in path.rglob("*") if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)
                print(f"- {label}: {files[0].relative_to(VAULT_ROOT) if files else 'none'}")
            else:
                print(f"- {label}: {'exists' if path.exists() else 'missing'}")


if __name__ == "__main__":
    main()
