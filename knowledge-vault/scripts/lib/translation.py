from __future__ import annotations

import json
import os
import re
import urllib.request
from abc import ABC, abstractmethod

from .config import load_config


GLOSSARY = {
    "AI": "人工智能",
    "Agent": "智能体",
    "agents": "智能体",
    "workflow": "工作流",
    "workflows": "工作流",
    "finance teams": "财务团队",
    "model": "模型",
    "models": "模型",
    "Codex": "Codex",
    "GitHub": "GitHub",
    "MCP": "MCP",
    "DeFi": "DeFi",
    "RWA": "RWA",
    "stablecoin": "稳定币",
    "stablecoins": "稳定币",
    "Ethereum": "Ethereum",
    "Solana": "Solana",
    "tokenized": "代币化",
    "security": "安全",
    "research": "研究",
    "report": "报告",
}


class TranslationProvider(ABC):
    provider_name: str

    @abstractmethod
    def translate_text(self, text: str) -> str:
        raise NotImplementedError


class MockTranslationProvider(TranslationProvider):
    provider_name = "mock"

    def translate_text(self, text: str) -> str:
        translated = text
        for en, zh in sorted(GLOSSARY.items(), key=lambda x: len(x[0]), reverse=True):
            translated = re.sub(rf"\b{re.escape(en)}\b", zh, translated, flags=re.I)
        return translated


class OpenAITranslationProvider(TranslationProvider):
    provider_name = "openai"

    def __init__(self, model: str, timeout: int) -> None:
        self.model = model
        self.timeout = timeout
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

    def translate_text(self, text: str) -> str:
        payload = {
            "model": self.model,
            "instructions": (
                "你是专业中英翻译和行业研究助理。"
                "将用户提供的英文内容翻译为简体中文。"
                "要求：保留 AI/Web3/金融专有名词的常用英文或中英对照；"
                "不要添加原文没有的信息；保持条理清晰；Markdown 格式输出。"
            ),
            "input": text,
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("output_text"):
            return data["output_text"].strip()
        parts = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    parts.append(content.get("text", ""))
        return "\n".join(parts).strip()


def get_translation_provider() -> TranslationProvider:
    config = load_config("translation_config.yaml")
    provider = str(config.get("provider", "mock")).lower()
    if provider == "openai":
        try:
            return OpenAITranslationProvider(
                model=str(config.get("model", "gpt-5.2")),
                timeout=int(config.get("timeout_seconds", 60)),
            )
        except Exception:
            if str(config.get("fallback_provider", "mock")).lower() == "mock":
                return MockTranslationProvider()
            raise
    return MockTranslationProvider()
