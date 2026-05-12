#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from lib.config import VAULT_ROOT, load_config
from lib.logging_utils import log_error, log_run, now_iso


USER_AGENT = "knowledge-vault-bot/1.0 (+local research collector)"
BAD_TITLES = {
    "skip to main content",
    "menu",
    "search",
    "home",
    "privacy policy",
    "terms",
    "careers",
    "contact",
}


def fetch_url(url: str, timeout: int = 25) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/rss+xml,application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def strip_tags(text: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_xml_date(value: str) -> str:
    if not value:
        return ""
    value = value.strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            parsed = dt.datetime.strptime(value.replace("Z", "+0000"), fmt)
            return parsed.date().isoformat()
        except Exception:
            continue
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    return match.group(0) if match else ""


def child_text(node: ET.Element, names: list[str]) -> str:
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return html.unescape(found.text.strip())
    for child in list(node):
        local = child.tag.split("}")[-1].lower()
        if local in names and child.text:
            return html.unescape(child.text.strip())
    return ""


def parse_feed(xml_text: str, source: dict[str, Any]) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    entries = []
    nodes = root.findall(".//item")
    if not nodes:
        nodes = [n for n in root.iter() if n.tag.split("}")[-1].lower() == "entry"]
    for item in nodes:
        title = child_text(item, ["title"])
        link = child_text(item, ["link"])
        if not link:
            link_node = next((c for c in list(item) if c.tag.split("}")[-1].lower() == "link"), None)
            if link_node is not None:
                link = link_node.attrib.get("href", "")
        summary = child_text(item, ["description", "summary", "content", "encoded"])
        published = child_text(item, ["pubDate", "published", "updated"])
        if title and link:
            entries.append({
                "title": title,
                "url": urllib.parse.urljoin(source.get("page_url") or source.get("feed_url"), link),
                "body": strip_tags(summary) or title,
                "published_at": parse_xml_date(published),
            })
    return entries


class LinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[dict[str, str]] = []
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            attrs_dict = {k.lower(): v or "" for k, v in attrs}
            self._href = attrs_dict.get("href", "")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            title = re.sub(r"\s+", " ", " ".join(self._text)).strip()
            url = urllib.parse.urljoin(self.base_url, self._href)
            if len(title) >= 8 and url.startswith("http"):
                self.links.append({"title": title, "url": url})
            self._href = ""
            self._text = []


def meta_description(html_text: str) -> str:
    patterns = [
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, re.I)
        if match:
            return html.unescape(match.group(1)).strip()
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html_text, re.S | re.I)
    text = " ".join(strip_tags(p) for p in paragraphs[:4])
    return text[:1200]


def parse_page_links(page_text: str, source: dict[str, Any]) -> list[dict[str, str]]:
    extractor = LinkExtractor(source["page_url"])
    extractor.feed(page_text)
    allow = source.get("link_allow", [])
    seen = set()
    entries = []
    for link in extractor.links:
        if link["title"].strip().lower() in BAD_TITLES:
            continue
        if link["title"].strip().lower().startswith("skip to "):
            continue
        if len(link["title"].split()) < 3 and not re.search(r"[\u4e00-\u9fff]", link["title"]):
            continue
        if allow and not any(token in link["url"] for token in allow):
            continue
        normalized = link["url"].split("#")[0].rstrip("/")
        if normalized in seen:
            continue
        seen.add(normalized)
        entries.append({
            "title": link["title"],
            "url": normalized,
            "body": f"自动采集自 {source['name']}。标题：{link['title']}",
            "published_at": "",
        })
    return entries


def enrich_entry(entry: dict[str, str]) -> dict[str, str]:
    try:
        page = fetch_url(entry["url"], timeout=18)
        desc = meta_description(page)
        if desc:
            entry["body"] = desc
    except Exception:
        pass
    return entry


def load_sources() -> list[dict[str, Any]]:
    path = VAULT_ROOT / "configs" / "sources_config.yaml"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = load_config("sources_config.yaml")
    return [s for s in data.get("sources", []) if s.get("enabled", True)]


def collect_source(source: dict[str, Any], limit: int) -> tuple[list[dict[str, str]], str]:
    errors = []
    entries: list[dict[str, str]] = []
    feed_url = source.get("feed_url")
    if feed_url:
        try:
            entries = parse_feed(fetch_url(feed_url), source)
        except Exception as exc:
            errors.append(f"feed failed: {exc}")
    if not entries and source.get("page_url"):
        try:
            entries = parse_page_links(fetch_url(source["page_url"]), source)
        except Exception as exc:
            errors.append(f"page failed: {exc}")
    entries = [enrich_entry(e) for e in entries[:limit]]
    return entries, "; ".join(errors)


def ingest_entry(source: dict[str, Any], entry: dict[str, str], dry_run: bool = False) -> dict[str, Any] | None:
    cmd = [
        sys.executable,
        str(VAULT_ROOT / "scripts" / "vault.py"),
        "ingest",
        "--title", entry["title"],
        "--body", entry["body"],
        "--url", entry["url"],
        "--source", source["name"],
        "--domain", source["domain"],
    ]
    if entry.get("published_at"):
        cmd.extend(["--published-at", entry["published_at"]])
    if dry_run:
        print(json.dumps({"source": source["name"], "entry": entry}, ensure_ascii=False))
        return
    completed = subprocess.run(cmd, cwd=VAULT_ROOT, check=True, capture_output=True, text=True, encoding="utf-8")
    if completed.stdout:
        print(completed.stdout, end="")
    try:
        return json.loads(completed.stdout)
    except Exception:
        return None


def run_sync() -> None:
    subprocess.run([sys.executable, str(VAULT_ROOT / "scripts" / "sync_markdown_to_db.py"), "--domain", "all"], cwd=VAULT_ROOT, check=True)
    subprocess.run([sys.executable, str(VAULT_ROOT / "scripts" / "sync_markdown_to_vector.py"), "--domain", "all"], cwd=VAULT_ROOT, check=True)


def parse_collected_at(value: str) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(value)
    except Exception:
        return None


def load_index_items() -> list[dict[str, Any]]:
    path = VAULT_ROOT / "metadata" / "index.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("items", [])


def items_since(start: str) -> list[dict[str, Any]]:
    start_dt = parse_collected_at(start)
    if start_dt is None:
        return []
    fresh = []
    for item in load_index_items():
        collected_at = parse_collected_at(item.get("collected_at", ""))
        if collected_at and collected_at >= start_dt:
            fresh.append(item)
    return fresh


def touched_items_since(start: str) -> list[dict[str, Any]]:
    start_dt = parse_collected_at(start)
    if start_dt is None:
        return []
    touched = []
    for item in load_index_items():
        collected_at = parse_collected_at(item.get("collected_at", ""))
        if collected_at and collected_at >= start_dt:
            touched.append(item)
            continue
        for related in item.get("related_sources", []):
            related_at = parse_collected_at(related.get("collected_at", ""))
            if related_at and related_at >= start_dt:
                touched.append(item)
                break
    return touched


def domain_health() -> dict[str, dict[str, int]]:
    from lib.db import connect, init_db
    from lib.markdown_utils import markdown_files
    from lib.vector_store import get_vector_store

    init_db()
    stats: dict[str, dict[str, int]] = {}
    with connect() as conn:
        for domain in ["ai", "web3"]:
            stats[domain] = {
                "markdown_files": len(markdown_files(domain)),
                "documents": conn.execute(
                    "SELECT COUNT(*) c FROM documents WHERE status='active' AND domain IN (?, 'cross')",
                    (domain,),
                ).fetchone()["c"],
                "chunks": conn.execute(
                    "SELECT COUNT(*) c FROM chunks WHERE domain IN (?, 'cross')",
                    (domain,),
                ).fetchone()["c"],
                "vectorized_chunks": get_vector_store(domain).count(),
                "failed_chunks": conn.execute(
                    "SELECT COUNT(*) c FROM chunks WHERE domain IN (?, 'cross') AND embedding_status='failed'",
                    (domain,),
                ).fetchone()["c"],
            }
    return stats


def report_line_for_item(item: dict[str, Any]) -> str:
    path = item.get("file_path", "")
    location = f"`{path}`" if path else "未生成文档"
    return (
        f"- **[{item.get('domain', '').upper()}] {item.get('title', 'Untitled')}** "
        f"（来源：{item.get('source', '未知')}，可信度：{item.get('credibility_level', 'N/A')}，"
        f"重要性：{item.get('importance_score', 'N/A')}/10）  \n"
        f"  摘要：{item.get('summary', '暂无摘要')}  \n"
        f"  位置：{location}"
    )


def generate_report(
    start: str,
    end: str,
    stats: dict[str, int],
    warnings: list[str],
) -> Path:
    fresh = items_since(start)
    touched = touched_items_since(start)
    high_confidence = sorted(
        [item for item in touched if item.get("credibility_level") in {"A", "B"}],
        key=lambda item: item.get("importance_score", 0),
        reverse=True,
    )[:8]
    health = domain_health()
    report_dir = VAULT_ROOT / "reports" / "daily"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{dt.date.today().isoformat()}.md"
    latest_path = VAULT_ROOT / "reports" / "latest.md"

    lines = [
        f"# AI / Web3 每日情报简报 - {dt.date.today().isoformat()}",
        "",
        "## 采集概况",
        "",
        f"- 运行时间：{start} 至 {end}",
        f"- 来源数：{stats['sources']}",
        f"- 拉取条目：{stats['entries']}",
        f"- 入库处理：{stats['ingested']}（新增 {stats.get('created', 0)}，重复更新 {stats.get('duplicate_updated', 0)}）",
        f"- 本轮新增到索引：{len(fresh)}",
        f"- 采集错误：{stats['errors']}",
        "",
        "## 当前知识库规模",
        "",
        f"- AI：文档 {health['ai']['documents']}，chunks {health['ai']['chunks']}，向量化 {health['ai']['vectorized_chunks']}，失败 chunks {health['ai']['failed_chunks']}",
        f"- Web3：文档 {health['web3']['documents']}，chunks {health['web3']['chunks']}，向量化 {health['web3']['vectorized_chunks']}，失败 chunks {health['web3']['failed_chunks']}",
        "",
        "## 失败或警告来源",
        "",
    ]
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- 无")

    lines.extend(["", "## 值得关注的高可信材料", ""])
    if high_confidence:
        lines.extend(report_line_for_item(item) for item in high_confidence)
    else:
        lines.append("- 本次没有 A/B 级材料。")

    lines.extend(["", "## 查看全部材料", ""])
    lines.extend([
        "- AI 原始材料：`ai/raw/`",
        "- AI 整理后材料：`ai/processed/`",
        "- Web3 原始材料：`web3/raw/`",
        "- Web3 整理后材料：`web3/processed/`",
        "- SQLite 数据库：`data/sqlite/knowledge.db`",
        "- 向量库：`data/vector/`",
    ])

    text = "\n".join(lines) + "\n"
    report_path.write_text(text, encoding="utf-8")
    latest_path.write_text(text, encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=["all", "ai", "web3"], default="all")
    parser.add_argument("--limit-per-source", type=int, default=3)
    parser.add_argument("--sync", action="store_true", help="sync SQLite and vector indexes after collection")
    parser.add_argument("--no-report", action="store_true", help="skip the Chinese collection report")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    start = now_iso()
    stats = {"sources": 0, "entries": 0, "ingested": 0, "errors": 0, "created": 0, "duplicate_updated": 0}
    warnings: list[str] = []
    for source in load_sources():
        if args.domain != "all" and source["domain"] != args.domain:
            continue
        stats["sources"] += 1
        try:
            entries, warning = collect_source(source, args.limit_per_source)
            if warning:
                warnings.append(f"{source['id']}: {warning}")
                log_error("collect_web", f"{source['id']}: {warning}")
            stats["entries"] += len(entries)
            for entry in entries:
                result = ingest_entry(source, entry, args.dry_run)
                if isinstance(result, dict) and result.get("status") in stats:
                    stats[result["status"]] += 1
                stats["ingested"] += 1
        except Exception as exc:
            stats["errors"] += 1
            warnings.append(f"{source.get('id')}: {exc}")
            log_error("collect_web", f"{source.get('id')}: {exc}")

    if args.sync and not args.dry_run:
        run_sync()
    end = now_iso()
    if not args.dry_run and not args.no_report:
        report_path = generate_report(start, end, stats, warnings)
        print(json.dumps({"report": str(report_path.relative_to(VAULT_ROOT)).replace("\\", "/")}, ensure_ascii=False))
    log_run("ingestion", [f"collect_web start={start} end={end} stats={stats}"])
    print(stats)


if __name__ == "__main__":
    main()
