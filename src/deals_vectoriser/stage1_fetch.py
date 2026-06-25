"""Stage 1 entry point: fetch recent Form D filings, print them, dump to data/filings.json.

No database, no embeddings — just structured SEC data you can inspect.

    python -m deals_vectoriser.stage1_fetch --since-days 2
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta

from rich.console import Console
from rich.table import Table

from .config import DEFAULT_LOOKBACK_DAYS, FILINGS_JSON
from .discover import discover
from .enrich import enrich_issuer
from .parse import parse_filing
from .sec_client import SecClient

console = Console()


def _fmt_money(v) -> str:
    if v is None:
        return "—"
    return f"${v:,.0f}"


def run(since_days: int, limit: int | None) -> list[dict]:
    end = date.today()
    start = end - timedelta(days=since_days)
    s, e = start.isoformat(), end.isoformat()

    with SecClient() as client:
        console.print(
            f"[bold]Discovering Form D filings[/bold] {s} → {e} via EDGAR full-text search…"
        )
        stubs = discover(client, s, e)
        console.print(f"  found [green]{len(stubs)}[/green] filings")
        if limit:
            stubs = stubs[:limit]
            console.print(f"  limited to first [yellow]{len(stubs)}[/yellow]")

        records: list[dict] = []
        cache: dict = {}
        with console.status("Fetching + parsing primary_doc.xml…") as status:
            for i, stub in enumerate(stubs, 1):
                try:
                    rec = parse_filing(client, stub)
                    enrich_issuer(client, rec, cache)
                    records.append(rec)
                except Exception as ex:  # keep going; report at end
                    console.print(
                        f"  [red]skip[/red] {stub['accession']}: {type(ex).__name__}: {ex}"
                    )
                status.update(f"Fetching + parsing… {i}/{len(stubs)}")

    _dump(records)
    _print_table(records)
    return records


def _dump(records: list[dict]) -> None:
    FILINGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    FILINGS_JSON.write_text(json.dumps(records, indent=2, default=str))
    console.print(
        f"\n[bold]Wrote[/bold] {len(records)} filings → [cyan]{FILINGS_JSON}[/cyan]"
    )


def _print_table(records: list[dict], show: int = 30) -> None:
    t = Table(title=f"Form D filings (showing {min(show, len(records))} of {len(records)})")
    t.add_column("Issuer", overflow="ellipsis", max_width=34)
    t.add_column("Industry", overflow="ellipsis", max_width=20)
    t.add_column("Offering", justify="right")
    t.add_column("Sold", justify="right")
    t.add_column("Min", justify="right")
    t.add_column("ST", justify="center")
    t.add_column("Exempt")
    t.add_column("Form")
    for r in records[:show]:
        offering = "Indefinite" if r.get("is_indefinite") else _fmt_money(r.get("total_offering_amount"))
        t.add_row(
            r.get("entity_name") or "—",
            r.get("industry_group") or "—",
            offering,
            _fmt_money(r.get("total_amount_sold")),
            _fmt_money(r.get("minimum_investment")),
            r.get("state_or_country") or "—",
            ",".join(r.get("federal_exemptions") or []) or "—",
            r.get("form_type") or "—",
        )
    console.print(t)


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage 1: fetch + show SEC Form D filings")
    ap.add_argument("--since-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    ap.add_argument("--limit", type=int, default=None, help="cap number of filings (for quick tests)")
    args = ap.parse_args()
    run(args.since_days, args.limit)


if __name__ == "__main__":
    main()
