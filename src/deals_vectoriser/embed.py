"""Embeddings via OpenRouter (OpenAI-compatible /embeddings endpoint)."""

from __future__ import annotations

import math

from openai import OpenAI

from .config import EMBED_MODEL, OPENROUTER_API_KEY, OPENROUTER_BASE_URL

_client: OpenAI | None = None


def _get() -> OpenAI:
    global _client
    if _client is None:
        if not OPENROUTER_API_KEY:
            raise RuntimeError("Set OPENROUTER_API_KEY in .env")
        _client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)
    return _client


def embed(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    """Embed texts in batches. Order preserved."""
    client = _get()
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        resp = client.embeddings.create(model=EMBED_MODEL, input=chunk)
        out.extend(d.embedding for d in sorted(resp.data, key=lambda d: d.index))
    return out


def embed_one(text: str) -> list[float]:
    return embed([text])[0]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0
