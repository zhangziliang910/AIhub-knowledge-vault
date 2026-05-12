#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from lib.embedding import get_embedding_provider


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    args = parser.parse_args()
    provider = get_embedding_provider()
    vector = provider.embed_text(args.text)
    print(json.dumps({"provider": provider.provider_name, "dimension": len(vector), "embedding": vector[:8]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
