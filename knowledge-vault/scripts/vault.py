#!/usr/bin/env python3
"""
Lightweight domain intelligence vault.

Storage:
- Markdown files for raw content, processed notes, reports, and project dossiers.
- JSON index for metadata and simple retrieval.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import textwrap
import uuid
from collections import Counter
from pathlib import Path
from typing import Any


VAULT_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = VAULT_ROOT / "metadata" / "index.json"

DOMAINS = ("ai", "web3")
DOMAIN_FOLDERS = (
    "raw", "processed", "daily", "weekly", "projects",
    "people", "companies", "concepts",
)
SHARED_FOLDERS = ("sources", "prompts", "templates")
LOG_FOLDERS = ("ingestion", "errors", "runs")

AI_KEYWORDS = {
    "ai", "artificial intelligence", "llm", "model", "agent", "rag",
    "openai", "anthropic", "claude", "chatgpt", "gpt", "gemini",
    "deepmind", "mistral", "llama", "nvidia", "inference", "training",
    "multimodal", "embedding", "benchmark", "transformer",
}

WEB3_KEYWORDS = {
    "web3", "crypto", "blockchain", "ethereum", "solana", "bitcoin",
    "defi", "dao", "nft", "token", "staking", "rollup", "layer2",
    "zk", "zero knowledge", "wallet", "stablecoin", "binance",
    "coinbase", "protocol", "smart contract",
}

PROJECT_ALIASES = {
    "openai": ("ai", "OpenAI"),
    "anthropic": ("ai", "Anthropic"),
    "claude": ("ai", "Anthropic"),
    "ethereum": ("web3", "Ethereum"),
    "solana": ("web3", "Solana"),
    "bitcoin": ("web3", "Bitcoin"),
}

SOURCE_LEVEL_HINTS = {
    "A": [
        "official", "公告", "官方", "paper", "论文", "arxiv", "github",
        "sec.gov", "regulation", "监管", "blog.ethereum.org",
        "openai.com", "anthropic.com", "solana.com",
    ],
    "B": [
        "the information", "wired", "techcrunch", "bloomberg", "reuters",
        "coindesk", "cointelegraph", "decrypt", "量子位", "机器之心",
    ],
    "C": ["twitter", "x.com", "reddit", "discord", "telegram", "kol", "社区"],
    "D": ["rumor", "爆料", "转载", "搬运", "unverified", "leak"],
}

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "are", "was",
    "were", "will", "about", "into", "over", "under", "after", "before",
    "一个", "以及", "可以", "已经", "可能", "进行", "通过", "对于", "关于",
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def slugify(text: str, max_len: int = 80) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text.lower(), flags=re.UNICODE)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned[:max_len].strip("-") or "untitled"


def tokenize(text: str) -> list[str]:
    lower = text.lower()
    latin = re.findall(r"[a-z0-9][a-z0-9\-]{1,}", lower)
    cjk = re.findall(r"[\u4e00-\u9fff]{2,}", lower)
    return [t for t in latin + cjk if t not in STOPWORDS]


def jaccard(a: str, b: str) -> float:
    sa, sb = set(tokenize(a)), set(tokenize(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def load_index() -> dict[str, Any]:
    if not INDEX_PATH.exists():
        return {"version": 1, "items": []}
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def save_index(index: dict[str, Any]) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ensure_directory_structure() -> None:
    for domain in DOMAINS:
        for folder in DOMAIN_FOLDERS:
            (VAULT_ROOT / domain / folder).mkdir(parents=True, exist_ok=True)
    for folder in SHARED_FOLDERS:
        (VAULT_ROOT / "shared" / folder).mkdir(parents=True, exist_ok=True)
    for folder in LOG_FOLDERS:
        (VAULT_ROOT / "logs" / folder).mkdir(parents=True, exist_ok=True)
    (VAULT_ROOT / "metadata").mkdir(parents=True, exist_ok=True)


def choose_domain(title: str, body: str, explicit_domain: str | None = None) -> str:
    if explicit_domain and explicit_domain in {"ai", "web3", "cross"}:
        return explicit_domain

    text = f"{title}\n{body}".lower()
    ai_score = sum(1 for kw in AI_KEYWORDS if kw in text)
    web3_score = sum(1 for kw in WEB3_KEYWORDS if kw in text)

    if ai_score and web3_score:
        return "cross"
    if web3_score > ai_score:
        return "web3"
    return "ai"


def credibility_level(source: str, url: str, body: str) -> str:
    text = f"{source} {url} {body[:500]}".lower()
    for level in ("A", "B", "C", "D"):
        if any(hint.lower() in text for hint in SOURCE_LEVEL_HINTS[level]):
            return level
    return "B"


def extract_entities(text: str) -> list[str]:
    known = {
        "OpenAI", "Anthropic", "Claude", "ChatGPT", "GPT-5", "GPT-4",
        "Google", "DeepMind", "Gemini", "Meta", "Llama", "Mistral",
        "NVIDIA", "Ethereum", "Solana", "Bitcoin", "Base", "Arbitrum",
        "Optimism", "Coinbase", "Binance",
    }
    found = {name for name in known if name.lower() in text.lower()}
    caps = re.findall(r"\b[A-Z][A-Za-z0-9]{2,}(?:\s+[A-Z][A-Za-z0-9]{2,})?\b", text)
    found.update(caps[:12])
    return sorted(found)


def extract_tags(text: str, domain: str) -> list[str]:
    candidates = []
    keyword_sets = []
    if domain in {"ai", "cross"}:
        keyword_sets.append(AI_KEYWORDS)
    if domain in {"web3", "cross"}:
        keyword_sets.append(WEB3_KEYWORDS)
    lower = text.lower()
    for kws in keyword_sets:
        candidates.extend(kw for kw in kws if kw in lower)
    return sorted(set(candidates))[:12]


def summarize(body: str, max_chars: int = 420) -> str:
    body = re.sub(r"\s+", " ", body).strip()
    if len(body) <= max_chars:
        return body
    sentences = re.split(r"(?<=[。.!?])\s+", body)
    output = ""
    for sentence in sentences:
        if len(output) + len(sentence) > max_chars:
            break
        output += sentence + " "
    return (output.strip() or body[:max_chars]).rstrip() + "..."


def key_points(body: str, limit: int = 5) -> list[str]:
    sentences = [s.strip() for s in re.split(r"(?<=[。.!?])\s+", body) if s.strip()]
    scored = []
    for s in sentences:
        score = len(set(tokenize(s))) + min(len(s) / 120, 2)
        scored.append((score, s))
    chosen = [s for _, s in sorted(scored, reverse=True)[:limit]]
    return chosen or [summarize(body, 180)]


def importance_score(title: str, body: str, credibility: str, tags: list[str]) -> int:
    text = f"{title} {body}".lower()
    score = 3
    score += {"A": 3, "B": 2, "C": 1, "D": 0}.get(credibility, 1)
    score += min(len(tags) // 2, 2)
    if any(w in text for w in ["launch", "release", "发布", "融资", "regulation", "监管", "mainnet", "模型"]):
        score += 1
    if any(w in text for w in ["openai", "anthropic", "ethereum", "solana"]):
        score += 1
    return max(1, min(score, 10))


def infer_type(title: str, body: str) -> str:
    text = f"{title} {body}".lower()
    if any(x in text for x in ["paper", "论文", "research", "arxiv"]):
        return "research"
    if any(x in text for x in ["launch", "release", "发布", "上线"]):
        return "product_update"
    if any(x in text for x in ["regulation", "监管", "sec", "policy", "政策"]):
        return "policy"
    if any(x in text for x in ["funding", "融资", "raises", "acquisition", "收购"]):
        return "business"
    return "news"


def domains_for_storage(domain: str) -> list[str]:
    return ["ai", "web3"] if domain == "cross" else [domain]


def frontmatter(data: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            rendered = "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in value) + "]"
        else:
            rendered = json.dumps(value, ensure_ascii=False)
        lines.append(f"{key}: {rendered}")
    lines.append("---")
    return "\n".join(lines)


def find_duplicate(index: dict[str, Any], title: str, url: str, summary_text: str) -> dict[str, Any] | None:
    for item in index["items"]:
        if url and item.get("url") == url:
            return item
        if jaccard(title, item.get("title", "")) >= 0.82:
            return item
        if summary_text and jaccard(summary_text, item.get("summary", "")) >= 0.78:
            return item
    return None


def append_duplicate(existing: dict[str, Any], title: str, url: str, source: str, note: str) -> None:
    processed_path = VAULT_ROOT / existing["file_path"]
    if processed_path.exists():
        addition = textwrap.dedent(f"""

        ## 相关来源 / 补充信息

        - 标题：{title}
        - 来源：{source}
        - 链接：{url or "N/A"}
        - 记录时间：{now_iso()}
        - 补充摘要：{summarize(note, 260)}
        """)
        processed_path.write_text(processed_path.read_text(encoding="utf-8") + addition, encoding="utf-8")

    related = existing.setdefault("related_sources", [])
    related.append({"title": title, "url": url, "source": source, "collected_at": now_iso()})


def write_raw(domain: str, item_id: str, title: str, body: str, meta: dict[str, Any]) -> Path:
    date = dt.date.today().isoformat()
    path = VAULT_ROOT / domain / "raw" / f"{date}-{slugify(title)}-{item_id[:8]}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"{frontmatter(meta)}\n\n# {title}\n\n{body.strip()}\n"
    path.write_text(content, encoding="utf-8")
    return path


def write_processed(domain: str, item_id: str, title: str, body: str, meta: dict[str, Any]) -> Path:
    date = dt.date.today().isoformat()
    path = VAULT_ROOT / domain / "processed" / f"{date}-{slugify(title)}-{item_id[:8]}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    points = key_points(body)
    impacts = infer_impacts(body, meta["domain"], meta["tags"])
    tracking = "是" if meta["importance_score"] >= 7 else "否"

    content = textwrap.dedent(f"""\
    {frontmatter(meta)}

    # {title}

    ## 基本信息

    - ID：{meta["id"]}
    - 领域：{meta["domain"]}
    - 类型：{meta["type"]}
    - 来源：{meta["source"]}
    - 链接：{meta["url"] or "N/A"}
    - 发布时间：{meta["published_at"] or "N/A"}
    - 收集时间：{meta["collected_at"]}
    - 来源可信度：{meta["credibility_level"]}
    - 重要性评分：{meta["importance_score"]}/10

    ## 核心摘要

    {meta["summary"]}

    ## 关键信息

    {format_bullets(points)}

    ## 可能影响

    {format_bullets(impacts)}

    ## 相关实体

    {format_bullets(meta["entities"] or ["待补充"])}

    ## 标签

    {", ".join(meta["tags"]) if meta["tags"] else "待补充"}

    ## 是否需要后续跟踪

    {tracking}
    """)
    path.write_text(content, encoding="utf-8")
    return path


def infer_impacts(body: str, domain: str, tags: list[str]) -> list[str]:
    impacts = []
    text = body.lower()
    if domain in {"ai", "cross"}:
        impacts.append("可能影响 AI 产品能力、模型路线或产业竞争格局。")
    if domain in {"web3", "cross"}:
        impacts.append("可能影响协议生态、资产叙事、开发者活动或监管预期。")
    if "regulation" in text or "监管" in text:
        impacts.append("需要关注合规约束、政策执行口径以及市场情绪变化。")
    if "github" in text or "open source" in text or "开源" in text:
        impacts.append("需要观察开发者采用速度、社区贡献和后续版本迭代。")
    if tags:
        impacts.append(f"相关标签显示该信息与 {', '.join(tags[:4])} 关系较强。")
    return impacts[:5] or ["影响暂不明确，建议在后续信息中交叉验证。"]


def format_bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def update_project_dossiers(stored_domains: list[str], meta: dict[str, Any], body: str) -> None:
    text = f"{meta['title']} {body}".lower()
    for alias, (preferred_domain, project_name) in PROJECT_ALIASES.items():
        if alias not in text:
            continue
        target_domains = [preferred_domain] if preferred_domain in stored_domains else stored_domains
        for domain in target_domains:
            path = VAULT_ROOT / domain / "projects" / f"{slugify(project_name)}.md"
            if not path.exists():
                path.write_text(
                    textwrap.dedent(f"""\
                    # {project_name}

                    ## 概览

                    待补充项目背景、产品线、核心团队、生态位置与长期观察指标。

                    ## 时间线
                    """),
                    encoding="utf-8",
                )
            addition = textwrap.dedent(f"""

            ### {meta["published_at"] or meta["collected_at"]} - {meta["title"]}

            - 来源：{meta["source"]}（可信度 {meta["credibility_level"]}）
            - 链接：{meta["url"] or "N/A"}
            - 摘要：{meta["summary"]}
            - 重要性：{meta["importance_score"]}/10
            """)
            path.write_text(path.read_text(encoding="utf-8") + addition, encoding="utf-8")


def ingest(args: argparse.Namespace) -> None:
    index = load_index()
    body = args.body or Path(args.body_file).read_text(encoding="utf-8")
    domain = choose_domain(args.title, body, args.domain)
    summary_text = summarize(body)

    duplicate = find_duplicate(index, args.title, args.url or "", summary_text)
    if duplicate:
        append_duplicate(duplicate, args.title, args.url or "", args.source, body)
        save_index(index)
        log_event("ingestion", f"duplicate updated: {duplicate['id']} - {args.title}")
        print(json.dumps({"status": "duplicate_updated", "id": duplicate["id"]}, ensure_ascii=False, indent=2))
        return

    item_id = uuid.uuid4().hex
    credibility = credibility_level(args.source, args.url or "", body)
    tags = extract_tags(f"{args.title}\n{body}", domain)
    entities = extract_entities(f"{args.title}\n{body}")
    meta = {
        "id": item_id,
        "domain": domain,
        "title": args.title,
        "source": args.source,
        "url": args.url or "",
        "published_at": args.published_at or "",
        "collected_at": now_iso(),
        "type": infer_type(args.title, body),
        "tags": tags,
        "entities": entities,
        "importance_score": importance_score(args.title, body, credibility, tags),
        "credibility_level": credibility,
        "summary": summary_text,
        "file_path": "",
    }

    stored_domains = domains_for_storage(domain)
    raw_paths = []
    processed_paths = []
    for storage_domain in stored_domains:
        raw_paths.append(write_raw(storage_domain, item_id, args.title, body, meta))
        processed_path = write_processed(storage_domain, item_id, args.title, body, meta)
        processed_paths.append(processed_path)

    meta["file_path"] = str(processed_paths[0].relative_to(VAULT_ROOT)).replace("\\", "/")
    meta["raw_paths"] = [str(p.relative_to(VAULT_ROOT)).replace("\\", "/") for p in raw_paths]
    meta["processed_paths"] = [str(p.relative_to(VAULT_ROOT)).replace("\\", "/") for p in processed_paths]
    index["items"].append(meta)
    save_index(index)
    update_project_dossiers(stored_domains, meta, body)
    log_event("ingestion", f"ingested: {item_id} - {args.title}")
    print(json.dumps({"status": "created", "id": item_id, "domain": domain, "paths": meta["processed_paths"]}, ensure_ascii=False, indent=2))


def log_event(kind: str, message: str) -> None:
    folder = VAULT_ROOT / "logs" / kind
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{dt.date.today().isoformat()}.log"
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{now_iso()} {message}\n")


def generate_daily(args: argparse.Namespace) -> None:
    date = args.date or dt.date.today().isoformat()
    index = load_index()
    for domain in DOMAINS:
        items = [
            item for item in index["items"]
            if domain in domains_for_storage(item["domain"]) and item.get("collected_at", "").startswith(date)
        ]
        path = VAULT_ROOT / domain / "daily" / f"{date}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_report("每日简报", domain, date, items), encoding="utf-8")
        print(path.relative_to(VAULT_ROOT))


def iso_week_range(year_week: str | None) -> tuple[str, int, dt.date, dt.date]:
    if year_week:
        year, week = re.match(r"(\d{4})-W(\d{1,2})", year_week).groups()  # type: ignore[union-attr]
    else:
        today = dt.date.today()
        iso = today.isocalendar()
        year, week = iso.year, iso.week
    year, week = int(year), int(week)
    start = dt.date.fromisocalendar(year, week, 1)
    end = dt.date.fromisocalendar(year, week, 7)
    return f"{year}-W{week:02d}", week, start, end


def generate_weekly(args: argparse.Namespace) -> None:
    label, _, start, end = iso_week_range(args.week)
    index = load_index()
    for domain in DOMAINS:
        items = []
        for item in index["items"]:
            collected = item.get("collected_at", "")[:10]
            if not collected:
                continue
            day = dt.date.fromisoformat(collected)
            if domain in domains_for_storage(item["domain"]) and start <= day <= end:
                items.append(item)
        path = VAULT_ROOT / domain / "weekly" / f"{label}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        subtitle = f"{start.isoformat()} 至 {end.isoformat()}"
        path.write_text(render_report("每周总结", domain, subtitle, items), encoding="utf-8")
        print(path.relative_to(VAULT_ROOT))


def render_report(report_type: str, domain: str, label: str, items: list[dict[str, Any]]) -> str:
    sorted_items = sorted(items, key=lambda x: x.get("importance_score", 0), reverse=True)
    top_tags = Counter(tag for item in sorted_items for tag in item.get("tags", [])).most_common(10)
    lines = [
        f"# {domain.upper()} {report_type} - {label}",
        "",
        "## 概览",
        "",
        f"- 入库数量：{len(sorted_items)}",
        f"- 高重要性信息：{sum(1 for i in sorted_items if i.get('importance_score', 0) >= 7)}",
        f"- 主要标签：{', '.join(tag for tag, _ in top_tags) if top_tags else '暂无'}",
        "",
        "## 重点信息",
        "",
    ]
    if not sorted_items:
        lines.append("- 暂无新增信息。")
    for item in sorted_items:
        lines.extend([
            f"### {item['title']}",
            "",
            f"- 来源：{item['source']}（可信度 {item['credibility_level']}）",
            f"- 链接：{item['url'] or 'N/A'}",
            f"- 重要性：{item['importance_score']}/10",
            f"- 标签：{', '.join(item.get('tags', [])) or '待补充'}",
            "",
            item["summary"],
            "",
        ])
    lines.extend([
        "## 后续跟踪",
        "",
        *[f"- {item['title']}" for item in sorted_items if item.get("importance_score", 0) >= 7],
    ])
    if lines[-1] == "":
        lines.append("- 暂无。")
    return "\n".join(lines).rstrip() + "\n"


def ask(args: argparse.Namespace) -> None:
    question_domain = choose_domain(args.question, "", args.domain)
    search_domains = domains_for_storage(question_domain)
    docs = collect_retrieval_docs(search_domains)
    scored = score_docs(args.question, docs)
    top = scored[: args.limit]
    answer = synthesize_answer(args.question, question_domain, top)
    print(answer)


def collect_retrieval_docs(domains: list[str]) -> list[dict[str, str]]:
    docs = []
    folders = ("daily", "weekly", "projects", "concepts", "processed")
    for domain in domains:
        for folder in folders:
            for path in (VAULT_ROOT / domain / folder).glob("*.md"):
                text = path.read_text(encoding="utf-8", errors="ignore")
                docs.append({
                    "domain": domain,
                    "folder": folder,
                    "path": str(path.relative_to(VAULT_ROOT)).replace("\\", "/"),
                    "text": text,
                })
    return docs


def score_docs(question: str, docs: list[dict[str, str]]) -> list[dict[str, Any]]:
    q_terms = Counter(tokenize(question))
    results = []
    for doc in docs:
        terms = Counter(tokenize(doc["text"]))
        overlap = sum(min(q_terms[t], terms[t]) for t in q_terms)
        if overlap == 0:
            continue
        norm = math.sqrt(sum(v * v for v in terms.values())) or 1
        score = overlap / norm
        snippet = best_snippet(question, doc["text"])
        results.append({**doc, "score": score, "snippet": snippet})
    return sorted(results, key=lambda d: d["score"], reverse=True)


def best_snippet(question: str, text: str, max_chars: int = 360) -> str:
    q = set(tokenize(question))
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return ""
    ranked = sorted(paragraphs, key=lambda p: len(q & set(tokenize(p))), reverse=True)
    return summarize(ranked[0], max_chars)


def synthesize_answer(question: str, domain: str, docs: list[dict[str, Any]]) -> str:
    lines = [
        f"# 回答：{question}",
        "",
        f"判断领域：{domain}",
        "",
    ]
    if not docs:
        lines.extend([
            "当前知识库没有检索到足够相关的沉淀内容。",
            "",
            "建议先录入相关材料，或扩大问题范围后重试。",
        ])
        return "\n".join(lines)

    lines.extend([
        "## 基于知识库的结论",
        "",
        "以下回答基于本地 Markdown 知识库的检索结果，尚未调用外部实时搜索。",
        "",
    ])
    for idx, doc in enumerate(docs, 1):
        lines.extend([
            f"{idx}. 证据来自 `{doc['path']}`",
            f"   - 摘要：{doc['snippet']}",
        ])
    lines.extend([
        "",
        "## 综合判断",
        "",
        "从已沉淀材料看，相关问题应优先结合上方证据判断：关注官方来源与高可信度材料，区分事实、推断和市场叙事。若证据来自日报/周报，应回溯 processed 笔记或项目档案确认原始来源。",
    ])
    return "\n".join(lines)


def init_indexes(args: argparse.Namespace) -> None:
    ensure_directory_structure()
    for domain in DOMAINS:
        index_path = VAULT_ROOT / domain / "index.md"
        if not index_path.exists():
            index_path.write_text(
                textwrap.dedent(f"""\
                # {domain.upper()} 知识库索引

                ## 使用方式

                - `raw/`：原始采集内容
                - `processed/`：清洗后的结构化笔记
                - `daily/`：每日简报
                - `weekly/`：每周总结
                - `projects/`：重点项目档案
                - `people/`：关键人物档案
                - `companies/`：公司与机构档案
                - `concepts/`：概念、术语与主题卡片
                """),
                encoding="utf-8",
            )
    if not INDEX_PATH.exists():
        save_index({"version": 1, "items": []})
    print("initialized")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Knowledge vault CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create base index files")
    p_init.set_defaults(func=init_indexes)

    p_ingest = sub.add_parser("ingest", help="ingest one intelligence item")
    p_ingest.add_argument("--title", required=True)
    p_ingest.add_argument("--body")
    p_ingest.add_argument("--body-file")
    p_ingest.add_argument("--url", default="")
    p_ingest.add_argument("--source", required=True)
    p_ingest.add_argument("--published-at", default="")
    p_ingest.add_argument("--domain", choices=["ai", "web3", "cross"], default=None)
    p_ingest.set_defaults(func=ingest)

    p_daily = sub.add_parser("daily", help="generate daily brief")
    p_daily.add_argument("--date", default=None)
    p_daily.set_defaults(func=generate_daily)

    p_weekly = sub.add_parser("weekly", help="generate weekly summary")
    p_weekly.add_argument("--week", default=None, help="format: YYYY-Wxx")
    p_weekly.set_defaults(func=generate_weekly)

    p_ask = sub.add_parser("ask", help="retrieve and answer from vault")
    p_ask.add_argument("question")
    p_ask.add_argument("--domain", choices=["ai", "web3", "cross"], default=None)
    p_ask.add_argument("--limit", type=int, default=5)
    p_ask.set_defaults(func=ask)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "command", None) == "ingest" and not (args.body or args.body_file):
        parser.error("ingest requires --body or --body-file")
    args.func(args)


if __name__ == "__main__":
    main()
