#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from lib.retrieval import retrieve


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    parser.add_argument("--domain", choices=["all", "ai", "web3", "cross", "unknown"], default="all")
    parser.add_argument("--top_k", type=int, default=8)
    parser.add_argument("--min-importance", type=int, default=None)
    parser.add_argument("--credibility", default="", help="comma separated levels, e.g. A,B")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    args = parser.parse_args()
    filters = {}
    if args.min_importance:
        filters["min_importance"] = args.min_importance
    if args.credibility:
        filters["credibility_levels"] = [x.strip() for x in args.credibility.split(",") if x.strip()]
    if args.start_date:
        filters["start_date"] = args.start_date
    if args.end_date:
        filters["end_date"] = args.end_date
    print(json.dumps(retrieve(args.question, args.domain, args.top_k, filters), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
