#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(script: str, *args: str) -> None:
    subprocess.check_call([sys.executable, str(ROOT / "scripts" / script), *args], cwd=ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Knowledge Vault daily entrypoint. Use this file for routine operations.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize SQLite tables.")
    sub.add_parser("daily", help="Run the full daily collection, ingestion, sync, and brief pipeline.")
    sub.add_parser("weekly", help="Run weekly brief, trend memory, expert profile, and sync.")
    sub.add_parser("health", help="Check directories, database, chunks, vector store, and pipeline state.")

    p_sync = sub.add_parser("sync", help="Sync Markdown to SQLite and vector store.")
    p_sync.add_argument("--domain", choices=["all", "ai", "web3"], default="all")
    p_sync.add_argument("--rebuild", action="store_true", help="Rebuild vector chunks for the selected domain.")

    p_collect = sub.add_parser("collect", help="Only collect configured sources into JSONL. No ingestion.")
    p_collect.add_argument("--domain", choices=["all", "ai", "web3"], default="all")
    p_collect.add_argument("--limit-per-source", type=int, default=5)

    p_ask = sub.add_parser("ask", help="Ask a RAG question against the vault.")
    p_ask.add_argument("question")

    p_search = sub.add_parser("search", help="Retrieve supporting chunks without generating an answer.")
    p_search.add_argument("question")
    p_search.add_argument("--domain", choices=["auto", "ai", "web3", "cross"], default="auto")
    p_search.add_argument("--top-k", type=int, default=8)

    args = parser.parse_args()

    if args.command == "init":
        run("db_init.py")
    elif args.command == "daily":
        run("run_daily_pipeline.py")
    elif args.command == "weekly":
        run("run_weekly_pipeline.py")
    elif args.command == "health":
        run("health_check.py")
    elif args.command == "sync":
        run("sync_markdown_to_db.py", "--domain", args.domain)
        vector_args = ["--domain", args.domain]
        if args.rebuild:
            vector_args.append("--rebuild")
        run("sync_markdown_to_vector.py", *vector_args)
    elif args.command == "collect":
        run("collect_sources.py", "--domain", args.domain, "--limit-per-source", str(args.limit_per_source))
    elif args.command == "ask":
        run("rag_answer.py", "--question", args.question)
    elif args.command == "search":
        domain = "all" if args.domain == "auto" else args.domain
        run("retrieve.py", "--question", args.question, "--domain", domain, "--top_k", str(args.top_k))


if __name__ == "__main__":
    main()
