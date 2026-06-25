"""Compose a natural-language 'deal description' per filing for embedding.

Form D is mostly structured/numeric — flattening it into one sentence gives the
embedding model something semantically rich to cluster on.
"""

from __future__ import annotations

# Federal exemption codes -> readable Reg D references.
_EXEMPTIONS = {
    "06b": "Reg D Rule 506(b)",
    "06c": "Reg D Rule 506(c)",
    "04": "Reg D Rule 504",
    "05": "Reg D Rule 505",
    "3C": "Investment Company Act 3(c)",
    "3C.1": "3(c)(1)",
    "3C.7": "3(c)(7)",
}


def _money(v) -> str | None:
    if v is None:
        return None
    try:
        return f"${float(v):,.0f}"
    except (ValueError, TypeError):
        return None


def _exemptions(codes) -> str:
    return ", ".join(_EXEMPTIONS.get(c, c) for c in (codes or []))


def compose(rec: dict) -> str:
    """Return a compact description from a parsed filing record."""
    name = rec.get("entity_name") or "An undisclosed issuer"
    etype = (rec.get("entity_type") or "").strip()
    juris = (rec.get("jurisdiction_of_inc") or "").title().strip()
    industry = rec.get("industry_group")
    year = rec.get("year_of_inc")

    # Who.
    who = name
    desc = " ".join(x for x in (juris, etype) if x)
    if desc:
        who += f", a {desc}"
    if industry:
        who += f" in {industry}"
    if year:
        who += f", founded {year}"
    parts = [who.rstrip(".") + "."]

    # The raise.
    raise_bits = []
    offering = "an indefinite amount" if rec.get("is_indefinite") else _money(rec.get("total_offering_amount"))
    exempt = _exemptions(rec.get("federal_exemptions"))
    if offering:
        s = f"Raising up to {offering}"
        if exempt:
            s += f" under {exempt}"
        raise_bits.append(s)
    sec_types = rec.get("security_types") or []
    if sec_types:
        raise_bits.append("offering " + ", ".join(sec_types).lower())
    mn = _money(rec.get("minimum_investment"))
    if mn:
        raise_bits.append(f"minimum investment {mn}")
    if raise_bits:
        parts.append("; ".join(raise_bits) + ".")

    # Traction.
    sold = _money(rec.get("total_amount_sold"))
    remaining = _money(rec.get("total_remaining"))
    n = rec.get("num_investors")
    accredited = "" if rec.get("has_non_accredited") else "accredited "
    trac = []
    if sold:
        t = f"{sold} sold"
        if n:
            t += f" to {n} {accredited}investor" + ("s" if n != 1 else "")
        trac.append(t)
    if remaining:
        trac.append(f"{remaining} remaining")
    if trac:
        parts.append("; ".join(trac) + ".")

    # Where.
    city = rec.get("city")
    state = rec.get("state_or_country")
    if city or state:
        parts.append("Based in " + ", ".join(x for x in (city, state) if x) + ".")

    # Who runs it.
    people = []
    for p in rec.get("related_persons", []):
        nm = p.get("full_name")
        roles = ", ".join(p.get("relationships") or [])
        if nm:
            people.append(f"{nm} ({roles})" if roles else nm)
    if people:
        parts.append("Key people: " + "; ".join(people) + ".")

    return " ".join(parts)
