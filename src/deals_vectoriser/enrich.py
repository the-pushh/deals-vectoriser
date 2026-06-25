"""Enrich a parsed filing with issuer metadata from data.sec.gov (adds SIC code)."""

from __future__ import annotations

import httpx

from .config import SUBMISSIONS_URL
from .sec_client import SecClient


def enrich_issuer(client: SecClient, rec: dict, cache: dict | None = None) -> dict:
    """Add sic_code, sic_description, ein, state_of_incorporation, former_names.

    The Form D XML has no SIC classification; the submissions API does. Cached per CIK.
    Mutates and returns `rec`. Failures are non-fatal (fields left None).
    """
    cik = rec["cik"].zfill(10)
    cache = cache if cache is not None else {}
    if cik in cache:
        data = cache[cik]
    else:
        try:
            data = client.get_json(SUBMISSIONS_URL.format(cik=cik))
        except httpx.HTTPStatusError:
            data = {}
        cache[cik] = data

    rec["sic_code"] = (data.get("sic") or None)
    rec["sic_description"] = (data.get("sicDescription") or None)
    rec["ein"] = (data.get("ein") or None)
    rec["state_of_incorporation"] = (data.get("stateOfIncorporation") or None)
    rec["former_names"] = [
        f["name"] for f in data.get("formerNames", []) if f.get("name")
    ]
    return rec
