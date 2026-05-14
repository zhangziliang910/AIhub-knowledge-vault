#!/usr/bin/env python3
from __future__ import annotations

import argparse

from lib.briefing import docs_for_week, top_terms, work_insights
from lib.config import VAULT_ROOT
from lib.logging_utils import log_run
from lib.pipeline_utils import iso_week_label


def update(domain: str, week: str | None = None) -> str:
    label = week or iso_week_label()
    docs = docs_for_week(domain, label)
    terms = top_terms(docs, 8)
    insights = work_insights(domain, docs)
    path = VAULT_ROOT / domain / "trend_memory.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else f"# {domain.upper()} Trend Memory\n"
    if f"## {label}" in existing:
        return path.relative_to(VAULT_ROOT).as_posix()
    block = [
        "",
        f"## {label}",
        "",
        "### 新增趋势",
        "",
        "- " + ("、".join(terms[:4]) if terms else "本周资料不足，暂不判断。"),
        "",
        "### 强化趋势",
        "",
        "- " + ("、".join(terms[4:8]) if len(terms) > 4 else "暂无足够证据。"),
        "",
        "### 减弱趋势",
        "",
        "- 暂无足够证据。",
        "",
        "### 重大事件",
        "",
        *[f"- {doc['title']}" for doc in docs[:5]],
        "",
        "### 风险信号",
        "",
        "- 自动归纳结果需要结合官方来源和后续材料验证。",
        "",
        "### 对用户项目的影响",
        "",
        *[f"- {item}" for item in insights],
        "",
        "### 下周继续观察",
        "",
        "- 跟踪本周高频主题是否进入项目、产品、监管或开发者生态层面的实际变化。",
        "",
    ]
    path.write_text(existing.rstrip() + "\n" + "\n".join(block), encoding="utf-8")
    log_run("expert_updates", [f"update_trend_memory domain={domain} week={label} docs={len(docs)}"])
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
