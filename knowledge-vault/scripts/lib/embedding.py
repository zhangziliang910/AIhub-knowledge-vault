from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

from .config import load_config


class EmbeddingProvider(ABC):
    provider_name: str

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


class MockEmbeddingProvider(EmbeddingProvider):
    provider_name = "mock"

    def __init__(self, dimension: int = 128) -> None:
        self.dimension = dimension

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


def get_embedding_provider() -> EmbeddingProvider:
    config = load_config("embedding_config.yaml")
    provider = str(config.get("provider", "mock")).lower()
    # The standard edition keeps provider selection isolated here. Add API
    # providers such as OpenAI, DashScope, Voyage, BGE, or Jina without touching
    # ingestion/retrieval business logic.
    if provider != "mock":
        return MockEmbeddingProvider(int(config.get("dimension", 128)))
    return MockEmbeddingProvider(int(config.get("dimension", 128)))
