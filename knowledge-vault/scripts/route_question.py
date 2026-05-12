#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from lib.routing import route


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    args = parser.parse_args()
    print(json.dumps(route(args.question), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
