"""Stage 3 entry point: compose deal-text per filing, embed via OpenRouter, store.

    python -m deals_vectoriser.stage3_embed          # embed only filings missing an embedding
    python -m deals_vectoriser.stage3_embed --all     # re-embed everything

Reads filings from Supabase (filings.raw), writes vectors to filing_embeddings.
Prints an educational demo (vector shape + cosine similarity between deals).
"""

from __future__ import annotations

import argparse

from rich.console import Console

from .config import EMBED_DIM, EMBED_MODEL
from .deal_text import compose
from .embed import cosine, embed
from .store import get_client

console = Console()


def _to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def _demo(rows: list[dict]) -> None:
    """Show what an embedding is + that similar deals score higher."""
    console.rule("[bold]Embedding demo[/bold]")
    sample = rows[0]
    text = compose(sample["raw"])
    console.print(f"\n[bold]Deal-text[/bold] ({sample['accession_number']}):")
    console.print(f"  [dim]{text}[/dim]\n")

    vec = embed([text])[0]
    console.print(f"Vector: [green]{len(vec)}[/green] dims (model {EMBED_MODEL})")
    preview = ", ".join(f"{x:+.4f}" for x in vec[:8])
    console.print(f"First 8: [{preview}, …]\n")

    # Group by industry to pick two similar + one different.
    by_ind: dict[str, dict] = {}
    for r in rows:
        ind = r["raw"].get("industry_group") or "?"
        by_ind.setdefault(ind, r)
    same_ind = next((i for i, _ in by_ind.items() if sum(
        1 for r in rows if (r["raw"].get("industry_group") or "?") == i) >= 2), None)

    if same_ind:
        pair = [r for r in rows if (r["raw"].get("industry_group") or "?") == same_ind][:2]
        other = next((r for r in rows if (r["raw"].get("industry_group") or "?") != same_ind), None)
        trio = pair + ([other] if other else [])
        labels = [f"{r['raw'].get('entity_name')} [{r['raw'].get('industry_group')}]" for r in trio]
        vecs = embed([compose(r["raw"]) for r in trio])
        console.print("[bold]Cosine similarity[/bold] (1.0 = identical):")
        console.print(f"  same industry : {labels[0]}  ~  {labels[1]}")
        console.print(f"    → [green]{cosine(vecs[0], vecs[1]):.3f}[/green]")
        if other:
            console.print(f"  diff industry : {labels[0]}  ~  {labels[2]}")
            console.print(f"    → [yellow]{cosine(vecs[0], vecs[2]):.3f}[/yellow]")
    console.rule()


def run(do_all: bool) -> None:
    client = get_client()
    filings = client.table("filings").select("accession_number, raw").execute().data
    if not filings:
        console.print("[red]No filings in DB. Run Stage 2 first.[/red]")
        raise SystemExit(1)

    done = {
        r["accession_number"]
        for r in client.table("filing_embeddings").select("accession_number").execute().data
    }
    todo = filings if do_all else [f for f in filings if f["accession_number"] not in done]
    console.print(
        f"{len(filings)} filings, {len(done)} already embedded → "
        f"embedding [green]{len(todo)}[/green]"
    )

    _demo(filings)

    if not todo:
        console.print("Nothing to embed. (use --all to re-embed)")
        return

    texts = [compose(f["raw"]) for f in todo]
    console.print(f"Embedding {len(texts)} deal-texts via OpenRouter…")
    vectors = embed(texts)
    assert all(len(v) == EMBED_DIM for v in vectors), "unexpected vector dim"

    rows = [
        {
            "accession_number": f["accession_number"],
            "content": t,
            "embedding": _to_pgvector(v),
            "model": EMBED_MODEL,
        }
        for f, t, v in zip(todo, texts, vectors)
    ]
    client.table("filing_embeddings").upsert(rows, on_conflict="accession_number").execute()
    console.print(f"[bold]Stored[/bold] {len(rows)} embeddings → filing_embeddings")


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage 3: embed filings via OpenRouter")
    ap.add_argument("--all", action="store_true", help="re-embed every filing")
    args = ap.parse_args()
    run(args.all)


if __name__ == "__main__":
    main()
