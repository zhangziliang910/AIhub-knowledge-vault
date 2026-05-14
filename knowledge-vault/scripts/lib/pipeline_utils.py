from __future__ import annotations

import datetime as dt
import hashlib
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

from .config import VAULT_ROOT, load_config
from .logging_utils import now_iso


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 "
    "aihot-skill/0.2.0 knowledge-vault-intelligence-system/1.0"
)
BAD_TITLES = {"skip to main content", "skip to footer", "menu", "search", "home", "privacy policy", "terms"}


def today_str() -> str:
    return dt.date.today().isoformat()


def iso_week_label(day: dt.date | None = None) -> str:
    day = day or dt.date.today()
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def flatten_sources(domain: str = "all") -> list[dict[str, Any]]:
    config = load_config("sources.yaml")
    output: list[dict[str, Any]] = []
    for source_domain, groups in config.get("sources", {}).items():
        if domain != "all" and source_domain != domain:
            continue
        for group, sources in groups.items():
            for source in sources:
                if not source.get("enabled", True):
                    continue
                output.append({**source, "domain": source_domain, "group": group})
    return output


def fetch_url_with_curl(url: str, timeout: int = 25, accept: str | None = None) -> str | None:
    command = [
        "curl.exe",
        "-L",
        "--silent",
        "--show-error",
        "--max-time",
        str(timeout),
        "-H",
        f"User-Agent: {USER_AGENT}",
    ]
    if accept:
        command.extend(["-H", f"Accept: {accept}"])
    command.append(url)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout


def fetch_url(url: str, timeout: int = 25, retries: int = 2, accept: str | None = None) -> str:
    last_error: Exception | None = None
    accept_header = accept or "text/html,application/rss+xml,application/atom+xml,application/xml;q=0.9,*/*;q=0.8"
    for _ in range(max(1, retries)):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": accept_header,
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except Exception as exc:
            last_error = exc
            curl_result = fetch_url_with_curl(url, timeout=timeout, accept=accept_header)
            if curl_result is not None:
                return curl_result
    raise last_error or RuntimeError(f"fetch failed: {url}")


def strip_tags(text: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_date(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    normalized = value.replace("Z", "+0000")
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(normalized, fmt).date().isoformat()
        except Exception:
            pass
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    return match.group(0) if match else ""


def child_text(node: ET.Element, names: set[str]) -> str:
    for child in node.iter():
        local = child.tag.split("}")[-1]
        if local in names and child.text:
            return html.unescape(child.text.strip())
    return ""


def parse_feed(xml_text: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    nodes = root.findall(".//item")
    if not nodes:
        nodes = [n for n in root.iter() if n.tag.split("}")[-1].lower() == "entry"]
    rows = []
    for node in nodes:
        title = child_text(node, {"title"})
        link = child_text(node, {"link"})
        if not link:
            for child in node.iter():
                if child.tag.split("}")[-1].lower() == "link":
                    link = child.attrib.get("href", "")
                    break
        excerpt = child_text(node, {"description", "summary", "content", "encoded"})
        published = child_text(node, {"pubDate", "published", "updated"})
        if title and link:
            rows.append(normalize_item(source, title, urllib.parse.urljoin(source.get("url", ""), link), strip_tags(excerpt), parse_date(published)))
    return rows


class LinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[dict[str, str]] = []
        self.href = ""
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            attrs_map = {k.lower(): v or "" for k, v in attrs}
            self.href = attrs_map.get("href", "")
            self.text = []

    def handle_data(self, data: str) -> None:
        if self.href:
            self.text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self.href:
            title = re.sub(r"\s+", " ", " ".join(self.text)).strip()
            url = urllib.parse.urljoin(self.base_url, self.href).split("#")[0].rstrip("/")
            if title and url.startswith("http"):
                self.links.append({"title": title, "url": url})
            self.href = ""
            self.text = []


def page_excerpt(page: str) -> str:
    for pattern in [
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
    ]:
        match = re.search(pattern, page, re.I)
        if match:
            return html.unescape(match.group(1)).strip()
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", page, re.S | re.I)
    return " ".join(strip_tags(p) for p in paragraphs[:3])[:1200]


def parse_webpage(page_text: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    extractor = LinkExtractor(source["url"])
    extractor.feed(page_text)
    allow = source.get("link_allow", [])
    rows = []
    seen = set()
    for link in extractor.links:
        title_lower = link["title"].lower()
        if title_lower in BAD_TITLES or title_lower.startswith("skip to "):
            continue
        if len(link["title"]) < 8:
            continue
        if allow and not any(token in link["url"] for token in allow):
            continue
        if link["url"] in seen:
            continue
        seen.add(link["url"])
        rows.append(normalize_item(source, link["title"], link["url"], f"自动采集自 {source['name']}：{link['title']}", ""))
    return rows


def normalize_item(source: dict[str, Any], title: str, url: str, excerpt: str, published_at: str) -> dict[str, Any]:
    title = str(title or "")
    url = str(url or "")
    excerpt = str(excerpt or "")
    published_at = str(published_at or "")
    item_id = hashlib.sha1(f"{url or title}".encode("utf-8")).hexdigest()
    return {
        "id": item_id,
        "title": title.strip(),
        "url": url.strip(),
        "source_name": source["name"],
        "source_type": source.get("type", source.get("group", "")),
        "source_group": source.get("group", ""),
        "domain": source["domain"],
        "credibility_level": source.get("credibility_level", "B"),
        "source_tags": source.get("tags", []),
        "published_at": published_at,
        "collected_at": now_iso(),
        "excerpt": excerpt.strip() or title.strip(),
        "raw": excerpt.strip() or title.strip(),
    }


def collect_from_source(source: dict[str, Any], limit: int) -> tuple[list[dict[str, Any]], str]:
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    if source.get("type") == "aihot_api":
        try:
            return collect_aihot(source, limit), ""
        except Exception as exc:
            return [], f"aihot api failed: {exc}"
    feed_url = source.get("feed_url")
    if feed_url:
        try:
            rows = parse_feed(fetch_url(feed_url), source)
        except Exception as exc:
            errors.append(f"feed failed: {exc}")
    if not rows:
        try:
            rows = parse_webpage(fetch_url(source["url"]), source)
        except Exception as exc:
            errors.append(f"page failed: {exc}")
    return rows[:limit], "; ".join(errors)


def collect_aihot(source: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    params = {
        "mode": source.get("mode", "selected"),
        "take": str(min(limit, int(source.get("take", 50)))),
    }
    url = source["url"]
    if "?" not in url:
        url = url + "?" + urllib.parse.urlencode(params)
    data = json.loads(fetch_url(url, timeout=25, accept="application/json"))
    rows: list[dict[str, Any]] = []
    for item in data.get("items", [])[:limit]:
        title = item.get("title") or item.get("title_en") or ""
        if not title:
            continue
        excerpt = item.get("summary") or title
        row = normalize_item(
            source,
            title=title,
            url=item.get("url", ""),
            excerpt=excerpt,
            published_at=parse_date(item.get("publishedAt", "")),
        )
        row["source_name"] = item.get("source") or source["name"]
        row["source_type"] = "aihot_api"
        row["source_tags"] = list(set(source.get("tags", []) + [item.get("category", "")]))
        row["title_en"] = item.get("title_en") or ""
        rows.append(row)
    return rows


def run_script(script: str, *args: str) -> None:
    subprocess.run([sys.executable, str(VAULT_ROOT / "scripts" / script), *args], cwd=VAULT_ROOT, check=True)


def load_user_context() -> dict[str, Any]:
    return load_config("expert_config.yaml").get("user_context", {})
