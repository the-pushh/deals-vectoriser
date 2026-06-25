# Deal Vectoriser

Find live private-investment deals from SEC filings, and search them in plain English.

When a private company raises money in the US (a startup, a fund, a real-estate deal), it files a **Form D** notice with the SEC. Each one names the business, the people behind it, the industry, how much they're raising, how much they've sold so far, and how much is still open. Deal Vectoriser pulls these filings every day, stores them in a database, and turns each deal into a searchable "embedding" so you can ask for things like *"healthcare startups raising over $1M"* and get sensible results — not just keyword matches.

## What it does

- **Collects** new Form D filings from SEC EDGAR (the day's deals, and recent ones).
- **Structures** each filing — company, location, industry, raise size, amount sold/remaining, the people, the brokers, the exemption used — into a clean database (Supabase / Postgres).
- **Understands** each deal by converting its description into a vector (embedding), so search works by *meaning*, not exact words.
- **Searches** from a simple terminal chat: type what you want, get the closest deals ranked by a match score.

It runs **forward-looking** — built to grow a corpus of *current* deals day by day, not to backfill all of history.

### What you can ask
The search understands plain language and pulls out filters automatically:

- `biotech seed round` — topic match
- `healthcare above $1M` — topic + minimum raise size
- `open real estate funds in texas` — topic + location
- `top 50 crypto pooled funds` — topic + how many results

Results show a **match %**, the company, industry, amount offered / sold / remaining, status (open vs fully subscribed), location, and the SEC exemption. Type **`more`** to load the next page.

> Note on "is the deal still open?": SEC filings have no explicit "closed" flag. We infer it — `fully_subscribed` when nothing's left, `open` otherwise — and track follow-up amendments. Treat it as a strong hint, not a guarantee.

## Running it locally

### 1. One-time setup
You'll need Python 3.10+ and accounts for [Supabase](https://supabase.com) (free) and [OpenRouter](https://openrouter.ai) (a few dollars of credit; embeddings cost fractions of a cent).

```bash
cd deals-vectoriser
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[db,embed,tui]'
```

Copy the example env file and fill it in:
```bash
cp .env.example .env
```
Set these in `.env`:
- `SEC_USER_AGENT` — anything like `your-app your-email` (SEC requires it, or it blocks you)
- `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` — from your Supabase project → Settings → API
- `OPENROUTER_API_KEY` — from openrouter.ai

The database tables live in `supabase/migrations/`. Apply them to your Supabase project once (via the Supabase dashboard SQL editor or the Supabase CLI) before the first run.

### 2. Fetch deals
Pull the latest filings, store them, and embed them — one command:
```bash
python -m deals_vectoriser.run --since-days 2
```
- `--since-days N` — how far back to look (default 2). Run it daily.
- `--limit N` — cap how many to fetch (handy for a quick test).
- `--skip-embed` — fetch and store only.

It's safe to re-run — nothing gets duplicated, and only new deals get embedded.

### 3. Search
```bash
python -m deals_vectoriser.tui
```
Type a query, press Enter, browse results, type `more` for the next page, `exit` to quit.

### 4. (Optional) Run it daily on a schedule
A ready-made wrapper and a **disabled** cron template are included:
```bash
scripts/run.sh 2            # run the pipeline manually
```
To automate it, see `deploy/crontab.example` — it has a commented daily line you can enable with `crontab -e`. Off by default; nothing runs on a schedule until you turn it on.

## How a deal flows through

```
SEC EDGAR  →  fetch & parse  →  Supabase (structured deal)  →  embedding  →  semantic search
```

That's it — one pipeline to collect deals, one terminal app to explore them.
