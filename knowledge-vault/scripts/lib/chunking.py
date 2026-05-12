from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .config import load_config
from .markdown_utils import parse_frontmatter


@dataclass
class Chunk:
    id: str
    document_id: str
    domain: str
    chunk_index: int
    chunk_text: str
    file_path: str
    heading: str
    token_count: int


def rough_token_count(text: str) -> int:
    latin = re.findall(r"[A-Za-z0-9_]+", text)
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    return len(latin) + len(cjk)


def split_markdown_sections(text: str) -> list[tuple[str, str]]:
    _, body = parse_frontmatter(text)
    matches = list(re.finditer(r"^(#{1,6})\s+(.+)$", body, re.M))
    if not matches:
        return [("", body.strip())] if body.strip() else []

    sections: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        heading = match.group(2).strip()
        sections.append((heading, body[start:end].strip()))
    return sections


def split_long_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        window = text[start:end]
        if end < len(text):
            cut = max(window.rfind("\n\n"), window.rfind("。"), window.rfind(". "))
            if cut > max_chars * 0.5:
                end = start + cut + 1
                window = text[start:end]
        chunks.append(window.strip())
        if end >= len(text):
            break
        start = max(0, end - overlap_chars)
    return [c for c in chunks if c]


def make_chunk_id(document_id: str, chunk_index: int, chunk_text: str) -> str:
    digest = hashlib.sha1(f"{document_id}:{chunk_index}:{chunk_text}".encode("utf-8")).hexdigest()
    return digest


def chunk_document(
    document_id: str,
    domain: str,
    file_path: str,
    text: str,
    max_chars: int | None = None,
    overlap_chars: int | None = None,
) -> list[Chunk]:
    config = load_config("embedding_config.yaml")
    max_chars = int(max_chars or config.get("max_chunk_chars", 1200))
    overlap_chars = int(overlap_chars or config.get("overlap_chars", 150))
    sections = split_markdown_sections(text)
    chunks: list[Chunk] = []
    for heading, section_text in sections:
        for piece in split_long_text(section_text, max_chars, overlap_chars):
            idx = len(chunks)
            chunks.append(
                Chunk(
                    id=make_chunk_id(document_id, idx, piece),
                    document_id=document_id,
                    domain=domain,
                    chunk_index=idx,
                    chunk_text=piece,
                    file_path=file_path,
                    heading=heading,
                    token_count=rough_token_count(piece),
                )
            )
    return chunks
