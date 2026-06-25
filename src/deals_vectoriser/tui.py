"""Plain terminal REPL to test semantic search — chat-style, line-based.

    python -m deals_vectoriser.tui

Type a query, get ranked deals printed inline. Ctrl-D or 'exit' to quit.
Needs OPENROUTER_API_KEY + Supabase creds in .env.
"""

from __future__ import annotations

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from rich.console import Console

from .deal_text import _EXEMPTIONS
from .search import DEFAULT_K, embed_query, fetch

console = Console(highlight=False)


def _money(v) -> str:
    if v is None:
        return "—"
    try:
        v = float(v)
    except (ValueError, TypeError):
        return "—"
    if v >= 1e9:
        return f"${v / 1e9:.1f}B"
    if v >= 1e6:
        return f"${v / 1e6:.1f}M"
    if v >= 1e3:
        return f"${v / 1e3:.0f}K"
    return f"${v:.0f}"


def _exempt(codes) -> str:
    return ", ".join(_EXEMPTIONS.get(c, c) for c in (codes or [])) or "—"


def _print_results(rows: list[dict], start: int = 1) -> None:
    for i, r in enumerate(rows, start):
        sim = r.get("similarity", 0) or 0
        name = r.get("entity_name") or "—"
        loc = " ".join(x for x in (r.get("city"), r.get("state_or_country")) if x) or "—"
        # line 1: rank, match% (cosine similarity), company
        console.print(
            f"  [bold cyan]{i:>2}[/bold cyan]  [green]{sim * 100:5.1f}%[/green]  [bold]{name}[/bold]"
        )
        # line 2: the facts, dimmed
        facts = (
            f"{r.get('industry_group') or '—'} · "
            f"{_money(r.get('total_offering_amount'))} offered, "
            f"{_money(r.get('total_amount_sold'))} sold, "
            f"{_money(r.get('total_remaining'))} left · "
            f"{r.get('status') or '—'} · {loc} · {_exempt(r.get('federal_exemptions'))}"
        )
        console.print(f"      [dim]{facts}[/dim]")
    console.print()


def _filter_summary(filters: dict) -> str:
    bits = []
    if "min_amount" in filters:
        bits.append(f"≥{_money(filters['min_amount'])}")
    if "max_amount" in filters:
        bits.append(f"≤{_money(filters['max_amount'])}")
    if "status_filter" in filters:
        bits.append(filters["status_filter"])
    if "state_filter" in filters:
        bits.append(filters["state_filter"])
    return " ".join(bits)


_PLACEHOLDER = "biotech seed round   ·   healthcare above $1M   ·   top 50 real estate funds in texas"


def main() -> None:
    console.print(
        "[bold]deals semantic search[/bold]  "
        "[dim]— Enter to search, Ctrl-D or 'exit' to quit[/dim]\n"
    )
    session: PromptSession = PromptSession()
    prompt = HTML('<b><ansigreen>›</ansigreen></b> ')
    placeholder = HTML(f'<style fg="#6b6b6b">{_PLACEHOLDER}</style>')
    prep: dict | None = None  # cached current query (vector + filters)
    page = DEFAULT_K          # page size
    offset = 0                # rows already shown for the cached query

    while True:
        try:
            q = session.prompt(prompt, placeholder=placeholder).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("[dim]bye[/dim]")
            break
        if not q:
            continue
        if q.lower() in ("exit", "quit", ":q"):
            console.print("[dim]bye[/dim]")
            break

        # "more" → next page of the cached query (no re-embed).
        if q.lower() in ("more", "m", "next", ":more", "..."):
            if not prep:
                console.print("  [dim]search something first[/dim]\n")
                continue
            try:
                with console.status("[dim]loading more…[/dim]", spinner="dots"):
                    rows = fetch(prep, page, offset)
            except Exception as ex:
                console.print(f"  [dim]no more[/dim] [dim italic]({type(ex).__name__})[/dim italic]\n")
                continue
            if not rows:
                console.print("  [dim]— no more results —[/dim]\n")
                continue
            _print_results(rows, start=offset + 1)
            offset += len(rows)
            if len(rows) == page:
                console.print("  [dim]type 'more' for the next page[/dim]\n")
            continue

        # New query.
        try:
            with console.status("[dim]searching…[/dim]", spinner="dots"):
                prep = embed_query(q)
                page = (prep["limit"] if prep else None) or DEFAULT_K
                rows = fetch(prep, page, 0) if prep else []
        except Exception as ex:
            console.print(f"  [dim]no matches[/dim] [dim italic]({type(ex).__name__})[/dim italic]\n")
            prep = None
            continue

        semantic = prep["semantic"] if prep else q
        summ = _filter_summary(prep["filters"] if prep else {})
        if summ or semantic != q:
            line = f"  [dim]→ semantic:[/dim] [italic]{semantic}[/italic]"
            if summ:
                line += f"   [dim]filters:[/dim] [yellow]{summ}[/yellow]"
            console.print(line)

        if not rows:
            console.print("  [dim]no matches[/dim]\n")
            offset = 0
            continue
        _print_results(rows, start=1)
        offset = len(rows)
        if len(rows) == page:
            console.print("  [dim]type 'more' for the next page[/dim]\n")


if __name__ == "__main__":
    main()
