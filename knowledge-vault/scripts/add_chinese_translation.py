#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

from lib.config import VAULT_ROOT
from lib.logging_utils import log_run
from lib.translation import get_translation_provider


def is_mostly_english(text: str) -> bool:
    letters = len(re.findall(r"[A-Za-z]", text))
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    return letters > 40 and letters > cjk * 2


def extract_section(text: str, heading: str) -> str:
    pattern = rf"## {re.escape(heading)}\s+(.*?)(?:\n\s*## |\Z)"
    match = re.search(pattern, text, re.S)
    return match.group(1).strip() if match else ""


def build_translation_block(text: str, provider) -> str:
    title_match = re.search(r"^\s*#\s+(.+)$", text, re.M)
    title = title_match.group(1).strip() if title_match else "英文材料"
    summary = extract_section(text, "核心摘要") or title
    key_info = extract_section(text, "关键信息")
    sentences = [s.strip(" -\n\t") for s in re.split(r"(?<=[.!?])\s+", summary) if s.strip()]
    if not sentences:
        sentences = [summary]
    translated_summary = provider.translate_text("\n".join(sentences[:5]))
    key_lines = []
    for line in key_info.splitlines():
        clean = line.strip(" -")
        if clean and is_mostly_english(clean):
            key_lines.append(clean)
    translated_keys = provider.translate_text("\n".join(f"- {x}" for x in key_lines[:8])) if key_lines else ""
    lines = [
        "",
        "## 中文翻译 / 中文要点",
        "",
        f"> 说明：英文原文保留在上方；本节由 `{provider.provider_name}` 翻译/译写生成。",
        "",
        f"### 标题翻译",
        "",
        provider.translate_text(title),
        "",
        "### 摘要翻译",
        "",
        translated_summary,
    ]
    if translated_keys:
        lines.extend(["", "### 关键信息翻译", "", translated_keys])
    return "\n".join(lines) + "\n"


def remove_existing_block(text: str) -> str:
    marker = "\n## 中文翻译 / 中文要点"
    idx = text.find(marker)
    if idx == -1:
        marker = "## 中文翻译 / 中文要点"
        idx = text.find(marker)
    return text[:idx].rstrip() if idx != -1 else text


def process_file(path: Path, provider, force: bool = False) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if "## 中文翻译 / 中文要点" in text and not force:
        return False
    if not is_mostly_english(text):
        return False
    base = remove_existing_block(text) if force else text.rstrip()
    path.write_text(base.rstrip() + "\n" + build_translation_block(base, provider), encoding="utf-8")
    return True


def files_for(domain: str, date: str | None) -> list[Path]:
    roots = ["ai", "web3"] if domain == "all" else [domain]
    paths: list[Path] = []
    for root in roots:
        for folder in ["raw", "processed"]:
            base = VAULT_ROOT / root / folder
            if not base.exists():
                continue
            pattern = f"{date}-*.md" if date else "*.md"
            paths.extend(base.glob(pattern))
    return paths


def run(domain: str = "all", date: str | None = None, force: bool = False) -> dict[str, int]:
    stats = {"checked": 0, "updated": 0}
    provider = get_translation_provider()
    for path in files_for(domain, date):
        stats["checked"] += 1
        if process_file(path, provider, force=force):
            stats["updated"] += 1
    stats["provider"] = provider.provider_name
    log_run("pipeline", [f"add_chinese_translation domain={domain} date={date} stats={stats}"])
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=["all", "ai", "web3"], default="all")
    parser.add_argument("--date", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(run(args.domain, args.date, args.force))


if __name__ == "__main__":
    main()
