#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from lib.pipeline_utils import collect_from_source, flatten_sources


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    for source in flatten_sources("all"):
        if source["name"] == args.source_name:
            rows, warning = collect_from_source(source, args.limit)
            print(json.dumps({"warning": warning, "items": rows}, ensure_ascii=False, indent=2))
            return
    raise SystemExit(f"source not found: {args.source_name}")


if __name__ == "__main__":
    main()
