#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys

from lib.config import VAULT_ROOT
from lib.logging_utils import log_error, log_run
from lib.pipeline_utils import read_jsonl, run_script, today_str


def ingest_domain(domain: str, date: str | None = None, sync: bool = True) -> dict[str, int]:
    day = date or today_str()
    path = VAULT_ROOT / "data" / "filtered" / day / f"{domain}-accepted.jsonl"
    rows = read_jsonl(path)
    stats = {"input": len(rows), "ingested": 0, "failed": 0, "ai": 0, "web3": 0, "cross": 0}
    for item in rows:
        body = item.get("raw") or item.get("excerpt") or item.get("title", "")
        cmd = [
            sys.executable,
            str(VAULT_ROOT / "scripts" / "vault.py"),
            "ingest",
            "--title", item.get("title", ""),
            "--body", body,
            "--url", item.get("url", ""),
            "--source", item.get("source_name", ""),
            "--domain", item.get("domain", domain),
        ]
        if item.get("published_at"):
            cmd.extend(["--published-at", item["published_at"]])
        try:
            subprocess.run(cmd, cwd=VAULT_ROOT, check=True, capture_output=True, text=True)
            stats["ingested"] += 1
            stats[item.get("domain", domain)] = stats.get(item.get("domain", domain), 0) + 1
        except Exception as exc:
            stats["failed"] += 1
            log_error("pipeline", f"ingest failed {item.get('title')}: {exc}")
    if sync:
        run_script("add_chinese_translation.py", "--domain", "all", "--date", day)
        run_script("sync_markdown_to_db.py", "--domain", "all")
        run_script("sync_markdown_to_vector.py", "--domain", "all")
    log_run("pipeline", [f"ingest_pipeline date={day} domain={domain} stats={stats}"])
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=["all", "ai", "web3"], default="all")
    parser.add_argument("--date", default=None)
    parser.add_argument("--no-sync", action="store_true")
    args = parser.parse_args()
    domains = ["ai", "web3"] if args.domain == "all" else [args.domain]
    total = {}
    for domain in domains:
        total[domain] = ingest_domain(domain, args.date, sync=not args.no_sync)
    print(total)


if __name__ == "__main__":
    main()
