"""Load parsed Form D records into Supabase. Idempotent (upsert on natural keys)."""

from __future__ import annotations

import os

from supabase import Client, create_client

# Columns mapped straight from a parsed record (parse.py output).
ISSUER_FIELDS = [
    "cik", "entity_name", "entity_type", "jurisdiction_of_inc",
    "within_five_years", "sic_code", "sic_description", "ein",
    "state_of_incorporation", "street1", "street2", "city",
    "state_or_country", "state_or_country_desc", "zip_code", "phone",
    "previous_names", "former_names",
]

FILING_FIELDS = [
    "accession_number", "cik", "form_type", "is_amendment", "filed_date",
    "date_of_first_sale", "yet_to_occur", "industry_group", "revenue_range",
    "federal_exemptions", "security_types", "more_than_one_year",
    "is_business_combination", "minimum_investment", "total_offering_amount",
    "is_indefinite", "total_amount_sold", "total_remaining",
    "has_non_accredited", "num_investors", "sales_commissions",
    "finders_fees", "use_of_proceeds", "filing_url",
]


def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env "
            "(service_role key from Supabase dashboard → Settings → API)."
        )
    return create_client(url, key)


def _int_or_none(v):
    try:
        return int(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def _issuer_row(rec: dict) -> dict:
    row = {k: rec.get(k) for k in ISSUER_FIELDS}
    row["year_of_inc"] = _int_or_none(rec.get("year_of_inc"))
    return row


def _filing_row(rec: dict) -> dict:
    row = {k: rec.get(k) for k in FILING_FIELDS}
    row["raw"] = rec  # full parsed doc for later reprocessing
    return row


def load(records: list[dict], client: Client | None = None, on_step=None) -> dict:
    """Upsert issuers + filings; replace child rows. Returns counts.

    on_step(label): optional callback fired before each sub-operation so callers
    can render progress.
    """
    client = client or get_client()

    def step(label: str) -> None:
        if on_step:
            on_step(label)

    # Issuers first (filings FK-reference them); dedupe by CIK.
    step("issuers")
    issuers = {r["cik"]: _issuer_row(r) for r in records}
    client.table("issuers").upsert(list(issuers.values()), on_conflict="cik").execute()

    step("filings")
    filings = [_filing_row(r) for r in records]
    client.table("filings").upsert(filings, on_conflict="accession_number").execute()

    # Children have surrogate keys -> delete-then-insert per accession for idempotency.
    step("related_persons")
    accs = [r["accession_number"] for r in records]
    client.table("related_persons").delete().in_("accession_number", accs).execute()
    client.table("recipients").delete().in_("accession_number", accs).execute()

    persons = [
        {"accession_number": r["accession_number"], **p}
        for r in records
        for p in r.get("related_persons", [])
    ]
    recips = [
        {"accession_number": r["accession_number"], **rc}
        for r in records
        for rc in r.get("recipients", [])
    ]
    if persons:
        client.table("related_persons").insert(persons).execute()
    if recips:
        client.table("recipients").insert(recips).execute()

    return {
        "issuers": len(issuers),
        "filings": len(filings),
        "related_persons": len(persons),
        "recipients": len(recips),
    }
