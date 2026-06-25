"""End-to-end pipeline: discover → parse → enrich → store → embed.

One idempotent command, built for a daily cron job. Safe to re-run: filings
upsert on their keys, embeddings are only computed for filings that lack one.

    python -m deals_vectoriser.run --since-days 2
    python -m deals_vectoriser.run --since-days 1 --limit 10   # quick test
    python -m deals_vectoriser.run --skip-embed                # fetch+store only
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from rich.console import Console, Group
from rich.live import Live
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text

from .config import DEFAULT_LOOKBACK_DAYS, EMBED_DIM, EMBED_MODEL
from .deal_text import compose
from .discover import discover
from .embed import embed
from .enrich import enrich_issuer
from .parse import parse_filing
from .sec_client import SecClient
from .store import get_client, load

console = Console()


def _to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def _progress() -> "Progress":
    from rich.progress import Progress

    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def run(since_days: int, limit: int | None = None, skip_embed: bool = False) -> dict:
    end = date.today()
    start = end - timedelta(days=since_days)
    s, e = start.isoformat(), end.isoformat()

    # 1. Fetch (discover + parse + enrich).
    with SecClient() as sec:
        with console.status(
            f"[bold cyan]\\[1/4][/bold cyan] Discovering Form D filings {s} → {e}…",
            spinner="dots",
        ):
            stubs = discover(sec, s, e)
        if limit:
            stubs = stubs[:limit]
        console.print(f"[bold cyan]\\[1/4][/bold cyan] discovered [green]{len(stubs)}[/green] filings")

        records: list[dict] = []
        skipped = 0
        cache: dict = {}
        prog = _progress()
        # static description -> bar stays fixed; current name lives on its own line below.
        task = prog.add_task("[bold]\\[2/4][/bold] parse + enrich", total=len(stubs))
        name_line = Text("", style="dim cyan")
        with Live(Group(prog, name_line), console=console, refresh_per_second=12):
            for stub in stubs:
                try:
                    rec = parse_filing(sec, stub)
                    enrich_issuer(sec, rec, cache)
                    records.append(rec)
                    name_line.plain = f"   → {rec.get('entity_name') or stub['accession']}"
                except Exception as ex:
                    skipped += 1
                    name_line.plain = f"   skip {stub['accession']}: {type(ex).__name__}"
                prog.advance(task)
    console.print(f"[bold]\\[2/4][/bold] parsed [green]{len(records)}[/green] filings" + (f", [yellow]{skipped}[/yellow] skipped" if skipped else ""))

    if not records:
        console.print("No filings in window. Done.")
        return {"filings": 0, "embedded": 0}

    # 2. Store (bar advances through each table sub-step).
    db = get_client()
    prog = _progress()
    task = prog.add_task("[bold magenta]\\[3/4][/bold magenta] store", total=4)
    store_line = Text("", style="dim magenta")
    with Live(Group(prog, store_line), console=console, refresh_per_second=12):

        def _step(label: str) -> None:
            store_line.plain = f"   → {label}"
            prog.advance(task)

        counts = load(records, client=db, on_step=_step)
    console.print(
        f"[bold magenta]\\[3/4][/bold magenta] stored "
        f"{counts['filings']} filings, {counts['issuers']} issuers, "
        f"{counts['related_persons']} people, {counts['recipients']} brokers"
    )

    # 3. Embed filings that don't yet have a vector (bar advances per batch).
    embedded = 0
    if skip_embed:
        console.print("[bold blue]\\[4/4][/bold blue] embed skipped (--skip-embed)")
    else:
        done = {
            r["accession_number"]
            for r in db.table("filing_embeddings").select("accession_number").execute().data
        }
        todo = [r for r in records if r["accession_number"] not in done]
        if not todo:
            console.print(f"[bold blue]\\[4/4][/bold blue] all {len(records)} filings already embedded")
        else:
            batch = 100
            with _progress() as prog:
                task = prog.add_task(
                    "[bold blue]\\[4/4][/bold blue] embed via OpenRouter", total=len(todo)
                )
                for i in range(0, len(todo), batch):
                    chunk = todo[i : i + batch]
                    texts = [compose(r) for r in chunk]
                    vectors = embed(texts)
                    assert all(len(v) == EMBED_DIM for v in vectors), "unexpected vector dim"
                    rows = [
                        {
                            "accession_number": r["accession_number"],
                            "content": t,
                            "embedding": _to_pgvector(v),
                            "model": EMBED_MODEL,
                        }
                        for r, t, v in zip(chunk, texts, vectors)
                    ]
                    db.table("filing_embeddings").upsert(rows, on_conflict="accession_number").execute()
                    embedded += len(rows)
                    prog.advance(task, len(chunk))
            console.print(f"[bold blue]\\[4/4][/bold blue] embedded [green]{embedded}[/green] new (of {len(records)})")

    console.print(f"[bold green]✓ Pipeline complete[/bold green] — {len(records)} filings, {embedded} new embeddings")
    return {"filings": len(records), "embedded": embedded}


def main() -> None:
    ap = argparse.ArgumentParser(description="deals-vectoriser end-to-end pipeline")
    ap.add_argument("--since-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    ap.add_argument("--limit", type=int, default=None, help="cap filings (testing)")
    ap.add_argument("--skip-embed", action="store_true")
    args = ap.parse_args()
    run(args.since_days, args.limit, args.skip_embed)


if __name__ == "__main__":
    main()
