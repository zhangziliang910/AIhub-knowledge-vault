#!/usr/bin/env python3
from __future__ import annotations

import argparse

from lib.briefing import docs_for_week, render_weekly_markdown
from lib.config import VAULT_ROOT
from lib.logging_utils import log_run
from lib.pipeline_utils import iso_week_label, run_script


def generate(week: str | None = None, sync: bool = True) -> dict:
    label = week or iso_week_label()
    outputs = {}
    for domain in ["ai", "web3"]:
        docs = docs_for_week(domain, label)
        markdown = render_weekly_markdown(domain, label, docs)
        path = VAULT_ROOT / domain / "weekly" / f"{label}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        outputs[domain] = path.relative_to(VAULT_ROOT).as_posix()
    if sync:
        run_script("sync_markdown_to_db.py", "--domain", "all")
        run_script("sync_markdown_to_vector.py", "--domain", "all")
    log_run("briefs", [f"generate_weekly_brief week={label} outputs={outputs}"])
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", default=None)
    parser.add_argument("--no-sync", action="store_true")
    args = parser.parse_args()
    print(generate(args.week, sync=not args.no_sync))


if __name__ == "__main__":
    main()
