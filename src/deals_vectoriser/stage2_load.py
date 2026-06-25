"""Stage 2 entry point: load data/filings.json (from Stage 1) into Supabase.

    python -m deals_vectoriser.stage2_load

Requires SUPABASE_URL and SUPABASE_SERVICE_KEY in .env.
"""

from __future__ import annotations

import json

from rich.console import Console

from .config import FILINGS_JSON
from .store import get_client, load

console = Console()


def main() -> None:
    if not FILINGS_JSON.exists():
        console.print(f"[red]No {FILINGS_JSON}. Run Stage 1 first.[/red]")
        raise SystemExit(1)

    records = json.loads(FILINGS_JSON.read_text())
    console.print(f"Loading [green]{len(records)}[/green] filings → Supabase…")
    counts = load(records, client=get_client())
    console.print("[bold]Done.[/bold] Upserted:")
    for table, n in counts.items():
        console.print(f"  {table}: [cyan]{n}[/cyan]")


if __name__ == "__main__":
    main()
