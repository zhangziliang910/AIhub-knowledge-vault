from __future__ import annotations

import re

from .config import load_config


def route(question: str) -> dict:
    config = load_config("domain_config.yaml")
    domains = config.get("domains", {})
    q = question.lower()
    ai_keywords = [str(k) for k in domains.get("ai", {}).get("keywords", [])]
    web3_keywords = [str(k) for k in domains.get("web3", {}).get("keywords", [])]
    cross_keywords = [str(k) for k in config.get("cross_keywords", [])]
    ai_hits = [k for k in ai_keywords if k.lower() in q]
    web3_hits = [k for k in web3_keywords if k.lower() in q]
    cross_hits = [k for k in cross_keywords if k.lower() in q]
    if cross_hits or (ai_hits and web3_hits):
        domain, reason, keywords = "cross", "问题同时包含 AI 与 Web3 相关线索。", cross_hits + ai_hits + web3_hits
    elif ai_hits:
        domain, reason, keywords = "ai", "问题主要涉及大模型、Agent、RAG、AI 产品或 AI 公司。", ai_hits
    elif web3_hits:
        domain, reason, keywords = "web3", "问题主要涉及区块链、公链、DeFi、RWA、稳定币或协议生态。", web3_hits
    else:
        domain, reason, keywords = "unknown", "未命中明确领域关键词，建议同时轻量检索 AI 与 Web3。", []
    filters = {}
    if re.search(r"A[/级 ]?B|可信|官方|高可信", question, re.I):
        filters["credibility_levels"] = ["A", "B"]
    return {"domain": domain, "reason": reason, "keywords": keywords, "suggested_filters": filters}
