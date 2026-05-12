#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from lib.chunking import chunk_document
from lib.config import VAULT_ROOT
from lib.db import connect, init_db
from lib.markdown_utils import is_vectorizable


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-id")
    parser.add_argument("--domain", choices=["all", "ai", "web3"], default="all")
    args = parser.parse_args()
    init_db()
    params = []
    where = "WHERE status = 'active'"
    if args.document_id:
        where += " AND id = ?"
        params.append(args.document_id)
    elif args.domain != "all":
        where += " AND domain IN (?, 'cross')"
        params.extend([args.domain])

    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM documents {where}", params).fetchall()
    output = []
    for row in rows:
        if not is_vectorizable(row["file_path"]):
            continue
        path = VAULT_ROOT / row["file_path"]
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_document(row["id"], row["domain"], row["file_path"], text)
        output.extend([chunk.__dict__ for chunk in chunks])
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
