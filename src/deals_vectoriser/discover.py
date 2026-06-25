"""Discover Form D accessions in a date range via EDGAR full-text search (efts)."""

from __future__ import annotations

from .config import EFTS_SEARCH_URL
from .sec_client import SecClient

_PAGE = 10  # efts returns 10 hits/page; page with &from=


def discover(
    client: SecClient, start_date: str, end_date: str, forms: str = "D"
) -> list[dict]:
    """Return de-duped filing stubs for forms=D (incl. D/A) filed in [start, end].

    Each stub: {accession, cik, display_name, file_date, form, biz_location}.
    Dates are YYYY-MM-DD.
    """
    out: dict[str, dict] = {}
    frm = 0
    while True:
        data = client.get_json(
            EFTS_SEARCH_URL,
            params={
                "q": "",
                "forms": forms,
                "startdt": start_date,
                "enddt": end_date,
                "from": frm,
            },
        )
        hits = data.get("hits", {}).get("hits", [])
        total = data.get("hits", {}).get("total", {}).get("value", 0)
        if not hits:
            break
        for h in hits:
            src = h.get("_source", {})
            accession = h["_id"].split(":", 1)[0]
            if accession in out:
                continue
            ciks = src.get("ciks") or [None]
            names = src.get("display_names") or [None]
            locs = src.get("biz_locations") or src.get("biz_states") or [None]
            out[accession] = {
                "accession": accession,
                "cik": ciks[0],
                "display_name": names[0],
                "file_date": src.get("file_date"),
                "form": src.get("form"),
                "biz_location": locs[0],
            }
        frm += len(hits)
        if frm >= total:
            break
    return list(out.values())
