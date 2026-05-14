#!/usr/bin/env python3
from __future__ import annotations

import argparse

from lib.briefing import docs_for_week, top_terms
from lib.config import VAULT_ROOT
from lib.logging_utils import log_run
from lib.pipeline_utils import iso_week_label, load_user_context


def profile_title(domain: str) -> str:
    return "AI Expert Profile" if domain == "ai" else "Web3 Expert Profile"


def default_focus(domain: str) -> list[str]:
    if domain == "ai":
        return ["AI Agent 基础设施", "MCP / Skill 生态", "RAG 与长期记忆", "企业知识库", "金融行业 AI 应用"]
    return ["稳定币与 RWA", "DeFi", "Ethereum / Solana", "Web3 信息协作", "去中心化身份与数据确权"]


def update(domain: str, week: str | None = None) -> str:
    label = week or iso_week_label()
    docs = docs_for_week(domain, label)
    terms = top_terms(docs, 10)
    ctx = load_user_context()
    projects = ctx.get("projects", [])
    focus = default_focus(domain)
    important_docs = docs[:8]
    content = [
        f"# {profile_title(domain)}",
        "",
        "## 当前重点关注方向",
        "",
        *[f"- {x}" for x in focus],
        "",
        "## 当前核心判断",
        "",
        "- " + ("本周资料不足，保持原有判断框架。" if not docs else f"近期高频主题包括：{', '.join(terms[:6])}。后续判断应优先结合 weekly 与 trend_memory。"),
        "",
        "## 当前方法论",
        "",
        "- 区分已归档事实、来源观点、系统推测和信息不足。",
        "- 高可信官方材料优先，媒体和社区材料作为趋势线索。",
        "- 日报记录信息流，周报和 trend_memory 负责沉淀判断。",
        "",
        "## 当前重要项目 / 公司 / 协议",
        "",
        *[f"- {doc['title']}" for doc in important_docs[:6]],
        "",
        "## 当前重要概念",
        "",
        *[f"- {term}" for term in terms[:8]],
        "",
        "## 当前不确定问题",
        "",
        "- 哪些高频主题会转化为真实产品、监管变化或业务机会。",
        "- 哪些材料只是短期噪音，需要后续验证。",
        "",
        "## 对用户工作的长期关注点",
        "",
        *[f"- {p}" for p in projects],
        "",
        f"## 最近更新时间",
        "",
        f"- {label}",
        "",
    ]
    path = VAULT_ROOT / domain / "expert_profile.md"
    path.write_text("\n".join(content), encoding="utf-8")
    log_run("expert_updates", [f"update_expert_profile domain={domain} week={label} docs={len(docs)}"])
    return path.relative_to(VAULT_ROOT).as_posix()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=["all", "ai", "web3"], default="all")
    parser.add_argument("--week", default=None)
    args = parser.parse_args()
    domains = ["ai", "web3"] if args.domain == "all" else [args.domain]
    print({domain: update(domain, args.week) for domain in domains})


if __name__ == "__main__":
    main()
