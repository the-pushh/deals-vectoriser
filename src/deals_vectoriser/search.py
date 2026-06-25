"""Hybrid semantic search: parse structured constraints from the query, embed the
rest, rank by cosine similarity with SQL filters applied."""

from __future__ import annotations

import re

from .embed import embed_one
from .store import get_client

_UNIT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}

_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}

_AMOUNT = r"\$?\s*(\d[\d.,]*)\s*(k|m|b|thousand|million|billion)?"
_MIN_RE = re.compile(r"(?:above|over|more than|greater than|at least|minimum|min|>=?)\s*" + _AMOUNT, re.I)
_MAX_RE = re.compile(r"(?:below|under|less than|at most|maximum|max|<=?)\s*" + _AMOUNT, re.I)
_COUNT_RE = re.compile(r"\b(?:top|first)\s+(\d{1,3})\b|\b(\d{1,3})\s+(?:results|deals|matches|companies)\b", re.I)

DEFAULT_K = 20
MAX_K = 100


def _to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def _amount(num: str, unit: str | None) -> float:
    return float(num.replace(",", "")) * _UNIT.get((unit or "").lower(), 1.0)


def parse_query(q: str) -> tuple[str, dict, int | None]:
    """Split free text into (semantic_text, filters, limit).

    filters keys: min_amount, max_amount, status_filter, state_filter (any may be absent).
    limit: requested result count ("top 30", "50 deals") or None.
    Matched constraint phrases are stripped so they don't pollute the embedding.
    """
    filters: dict = {}
    text = q
    spans: list[tuple[int, int]] = []
    limit: int | None = None

    mc = _COUNT_RE.search(text)
    if mc:
        limit = max(1, min(MAX_K, int(mc.group(1) or mc.group(2))))
        spans.append((mc.start(), mc.end()))

    for rx, key in ((_MAX_RE, "max_amount"), (_MIN_RE, "min_amount")):
        m = rx.search(text)
        if m:
            filters[key] = _amount(m.group(1), m.group(2))
            spans.append((m.start(), m.end()))

    if re.search(r"fully\s*subscribed|already\s*closed|filled|completed", text, re.I):
        filters["status_filter"] = "fully_subscribed"
    elif re.search(r"still\s*open|still\s*raising|currently\s*raising|accepting", text, re.I):
        filters["status_filter"] = "open"

    for name, code in _STATES.items():
        if re.search(rf"\b{name}\b", text, re.I):
            filters["state_filter"] = code
            break
    else:
        m = re.search(r"\bin\s+([A-Z]{2})\b", text)
        if m:
            filters["state_filter"] = m.group(1)

    # Strip matched spans (count + amounts) from the semantic text.
    for a, b in sorted(spans, reverse=True):
        text = text[:a] + text[b:]
    text = re.sub(r"\s+", " ", text).strip(" .,") or q
    return text, filters, limit


def embed_query(query: str) -> dict | None:
    """Parse + embed a query once. Returned dict is reusable for paged fetch()."""
    query = (query or "").strip()
    if not query:
        return None
    semantic, filters, limit = parse_query(query)
    return {
        "vector": _to_pgvector(embed_one(semantic)),
        "filters": filters,
        "semantic": semantic,
        "limit": limit,
    }


def fetch(prep: dict, k: int, offset: int = 0) -> list[dict]:
    """Fetch one page of matches for an already-embedded query."""
    params = {
        "query_embedding": prep["vector"],
        "match_count": k,
        "match_offset": offset,
        **prep["filters"],
    }
    return get_client().rpc("match_deals", params).execute().data or []


def search(query: str, k: int = DEFAULT_K) -> tuple[list[dict], dict, str]:
    """One-shot search (first page). k is the fallback count when the query
    doesn't request one (e.g. 'top 30')."""
    prep = embed_query(query)
    if not prep:
        return [], {}, ""
    rows = fetch(prep, prep["limit"] or k, 0)
    return rows, prep["filters"], prep["semantic"]
