#!/usr/bin/env python3
from __future__ import annotations

import argparse

from lib.config import VAULT_ROOT, load_config
from lib.logging_utils import log_error, log_run, now_iso
from lib.pipeline_utils import collect_from_source, flatten_sources, today_str, write_jsonl


def collect(domain: str, limit_per_source: int | None = None) -> dict[str, int]:
    ingestion_config = load_config("ingestion_config.yaml")
    limit = int(limit_per_source or ingestion_config.get("max_items_per_source", 5))
    day = today_str()
    by_domain = {"ai": [], "web3": []}
    stats = {"sources": 0, "items": 0, "errors": 0}
    for source in flatten_sources(domain):
        stats["sources"] += 1
        try:
            rows, warning = collect_from_source(source, limit)
            if warning:
                stats["errors"] += 1
                log_error("collection", f"{source['name']}: {warning}")
            by_domain[source["domain"]].extend(rows)
            stats["items"] += len(rows)
        except Exception as exc:
            stats["errors"] += 1
            log_error("collection", f"{source.get('name')}: {exc}")
    for item_domain, rows in by_domain.items():
        if domain != "all" and item_domain != domain:
            continue
        write_jsonl(VAULT_ROOT / "data" / "collections" / day / f"{item_domain}.jsonl", rows)
    log_run("collection", [f"collect_sources start={now_iso()} domain={domain} stats={stats}"])
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=["all", "ai", "web3"], default="all")
    parser.add_argument("--limit-per-source", type=int, default=None)
    args = parser.parse_args()
    print(collect(args.domain, args.limit_per_source))


if __name__ == "__main__":
    main()
