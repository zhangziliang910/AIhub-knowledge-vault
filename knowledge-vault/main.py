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
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    p_db = sub.add_parser("sync-db")
    p_db.add_argument("--domain", choices=["all", "ai", "web3"], default="all")
    p_vec = sub.add_parser("sync-vector")
    p_vec.add_argument("--domain", choices=["all", "ai", "web3"], default="all")
    p_vec.add_argument("--rebuild", action="store_true")
    p_ask = sub.add_parser("ask")
    p_ask.add_argument("question")
    p_health = sub.add_parser("health")
    p_collect = sub.add_parser("collect")
    p_collect.add_argument("--domain", choices=["all", "ai", "web3"], default="all")
    p_collect.add_argument("--limit-per-source", type=int, default=3)
    p_collect.add_argument("--sync", action="store_true")
    args = parser.parse_args()
    if args.command == "init":
        run("db_init.py")
    elif args.command == "sync-db":
        run("sync_markdown_to_db.py", "--domain", args.domain)
    elif args.command == "sync-vector":
        extra = ["--rebuild"] if args.rebuild else []
        run("sync_markdown_to_vector.py", "--domain", args.domain, *extra)
    elif args.command == "ask":
        run("rag_answer.py", "--question", args.question)
    elif args.command == "health":
        run("health_check.py")
    elif args.command == "collect":
        extra = ["--sync"] if args.sync else []
        run("collect_web.py", "--domain", args.domain, "--limit-per-source", str(args.limit_per_source), *extra)


if __name__ == "__main__":
    main()
