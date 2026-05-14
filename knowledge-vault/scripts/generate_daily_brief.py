#!/usr/bin/env python3
from __future__ import annotations

import argparse

from lib.briefing import docs_for_date, render_daily_markdown, write_daily_outputs
from lib.logging_utils import log_run
from lib.pipeline_utils import run_script, today_str


def generate(date: str | None = None, sync: bool = True) -> dict:
    day = date or today_str()
    outputs = {}
    for domain in ["ai", "web3"]:
        docs = docs_for_date(domain, day)
        markdown = render_daily_markdown(domain, day, docs)
        outputs[domain] = write_daily_outputs(domain, day, markdown)
    if sync:
        run_script("sync_markdown_to_db.py", "--domain", "all")
        run_script("sync_markdown_to_vector.py", "--domain", "all")
    log_run("briefs", [f"generate_daily_brief date={day} outputs={outputs}"])
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--no-sync", action="store_true")
    args = parser.parse_args()
    print(generate(args.date, sync=not args.no_sync))


if __name__ == "__main__":
    main()
