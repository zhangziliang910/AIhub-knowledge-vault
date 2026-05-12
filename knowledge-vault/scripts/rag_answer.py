#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import uuid

from lib.db import connect, init_db
from lib.logging_utils import log_run, now_iso
from lib.retrieval import retrieve
from lib.routing import route


def latest_collected_at() -> str:
    with connect() as conn:
        row = conn.execute("SELECT MAX(collected_at) latest FROM documents WHERE status = 'active'").fetchone()
    return row["latest"] if row and row["latest"] else "暂无收录记录"


def low_credibility_note(level: str) -> str:
    if level in {"C", "D"}:
        return "该信息来自社交媒体 / KOL / 社区讨论或未验证来源，需进一步验证。"
    return ""


def build_answer(question: str, route_info: dict, results: list[dict]) -> str:
    def low_information(item: dict) -> bool:
        text = item["chunk_text"]
        path = item["file_path"]
        return (
            "暂无新增信息" in text
            or "入库数量：0" in text
            or item["file_path"].endswith("index.md")
            or (("/daily/" in path or "/weekly/" in path or "\\daily\\" in path or "\\weekly\\" in path) and ("每日简报" in text or "每周总结" in text))
        )

    if not results or all(low_information(item) for item in results):
        return (
            "## 结论\n\n"
            "当前知识库资料不足，无法基于已归档材料给出可靠回答。\n\n"
            "## 依据材料\n\n"
            "- 未检索到足够相关的本地资料；当前命中的材料多为空简报或目录索引，不能作为事实依据。\n\n"
            "## 后续可跟踪方向\n\n"
            "- 补充官方公告、项目博客、研究报告或高可信行业媒体材料后重新检索。\n"
        )

    latest = latest_collected_at()
    sources = []
    facts = []
    caveats = []
    for idx, item in enumerate(results, 1):
        note = low_credibility_note(item["credibility_level"])
        if note:
            caveats.append(f"- {item['title']}：{note}")
        sources.append(
            f"{idx}. `{item['file_path']}`：{item['title']}，来源 {item['source'] or '未标注'}，"
            f"可信度 {item['credibility_level']}，重要性 {item['importance_score']}/5。"
        )
        snippet = item["chunk_text"].replace("\n", " ")
        facts.append(f"- {snippet[:260]}{'...' if len(snippet) > 260 else ''}")

    return "\n".join([
        "## 结论",
        "",
        f"问题被路由为 `{route_info['domain']}`。基于当前知识库检索结果，可以先给出谨慎结论：相关判断应以上述已归档材料为准；若涉及趋势或未来影响，下面的分析属于系统推测而非已确认事实。",
        "",
        "## 依据材料",
        "",
        *sources,
        "",
        "## 关键事实",
        "",
        *facts[:6],
        "",
        "## 分析判断",
        "",
        "已归档事实主要来自检索到的 Markdown 笔记、项目档案、日报或周报。来源观点需要结合其可信度判断；A/B 级来源可作为主要依据，C/D 级来源仅适合作为线索。系统推测部分建议在后续采集到更多材料后再修正。",
        "",
        "## 风险与不确定性",
        "",
        *(caveats or ["- 暂未发现明显低可信来源，但仍需关注材料是否过期或是否缺少官方确认。"]),
        f"- 时间敏感提示：知识库最新收录时间为 {latest}。",
        "",
        "## 后续可跟踪方向",
        "",
        "- 继续补充官方公告、GitHub、论文、监管文件和项目博客。",
        "- 对高重要性主题建立项目或概念档案，避免只依赖日报碎片。",
    ])


def save_question(question: str, routed_domain: str, answer: str, results: list[dict]) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            "INSERT INTO questions(id,question,routed_domain,answer,used_document_ids,created_at) VALUES(?,?,?,?,?,?)",
            (
                uuid.uuid4().hex,
                question,
                routed_domain,
                answer,
                json.dumps(sorted({r["document_id"] for r in results}), ensure_ascii=False),
                now_iso(),
            ),
        )
        conn.commit()


def answer_question(question: str, top_k: int = 8) -> str:
    route_info = route(question)
    domain = route_info["domain"]
    retrieval_domain = domain if domain != "unknown" else "all"
    results = retrieve(question, retrieval_domain, top_k, route_info.get("suggested_filters", {}))
    answer = build_answer(question, route_info, results)
    save_question(question, domain, answer, results)
    log_run("retrieval", [f"rag_answer domain={domain} results={len(results)} question={question}"])
    return answer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    parser.add_argument("--top_k", type=int, default=8)
    args = parser.parse_args()
    print(answer_question(args.question, args.top_k))


if __name__ == "__main__":
    main()
