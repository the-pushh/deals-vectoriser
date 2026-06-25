"""Fetch + parse a Form D primary_doc.xml into a flat, JSON-serialisable dict."""

from __future__ import annotations

from lxml import etree

from .config import ARCHIVES_BASE
from .sec_client import SecClient

# securityTypes flag tag -> human label
_SECURITY_TYPES = {
    "isEquityType": "Equity",
    "isDebtType": "Debt",
    "isOptionToAcquireType": "Option/Warrant",
    "isSecurityToBeAcquiredType": "Security to be acquired",
    "isPooledInvestmentFundType": "Pooled investment fund interests",
    "isTenantInCommonType": "Tenant-in-common",
    "isMineralPropertyType": "Mineral property",
    "isOtherType": "Other",
}


def filing_url(cik: str, accession: str) -> str:
    """Build the primary_doc.xml URL. cik -> int dir, accession -> no-dash dir."""
    cik_int = str(int(cik))
    acc_nodash = accession.replace("-", "")
    return f"{ARCHIVES_BASE}/{cik_int}/{acc_nodash}/primary_doc.xml"


def _strip_ns(root: etree._Element) -> etree._Element:
    """Form D docs are usually namespace-less, but strip any to be safe."""
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    etree.cleanup_namespaces(root)
    return root


def _text(node, path: str) -> str | None:
    if node is None:
        return None
    v = node.findtext(path)
    if v is None:
        return None
    v = v.strip()
    return v or None


def _bool(node, path: str) -> bool | None:
    v = _text(node, path)
    if v is None:
        return None
    return v.lower() == "true"


def _money(node, path: str):
    """Return (value_or_None, is_indefinite). Non-numeric (e.g. 'Indefinite') -> (None, True)."""
    v = _text(node, path)
    if v is None:
        return None, False
    raw = v.replace(",", "").replace("$", "").strip()
    neg = raw.startswith("(") and raw.endswith(")")  # accounting negatives
    raw = raw.strip("()")
    try:
        num = float(raw)
        return (-num if neg else num), False
    except ValueError:
        return None, True


def parse_filing(client: SecClient, stub: dict) -> dict:
    """Fetch + parse one filing. `stub` comes from discover()."""
    url = filing_url(stub["cik"], stub["accession"])
    xml = client.get_text(url)
    root = _strip_ns(etree.fromstring(xml.encode("utf-8")))

    issuer = root.find("primaryIssuer")
    addr = issuer.find("issuerAddress") if issuer is not None else None
    offering = root.find("offeringData")

    offer_amt, offer_indef = _money(offering, "offeringSalesAmounts/totalOfferingAmount")

    rec: dict = {
        # identifiers
        "accession_number": stub["accession"],
        "cik": str(int(stub["cik"])),
        "form_type": _text(root, "submissionType") or stub.get("form"),
        "is_amendment": _bool(offering, "typeOfFiling/newOrAmendment/isAmendment"),
        "filed_date": stub.get("file_date"),
        "filing_url": url,
        # issuer
        "entity_name": _text(issuer, "entityName"),
        "entity_type": _text(issuer, "entityType"),
        "jurisdiction_of_inc": _text(issuer, "jurisdictionOfInc"),
        "year_of_inc": _text(issuer, "yearOfInc/value"),
        "within_five_years": _bool(issuer, "yearOfInc/withinFiveYears"),
        "phone": _text(issuer, "issuerPhoneNumber"),
        "street1": _text(addr, "street1"),
        "street2": _text(addr, "street2"),
        "city": _text(addr, "city"),
        "state_or_country": _text(addr, "stateOrCountry"),
        "state_or_country_desc": _text(addr, "stateOrCountryDescription"),
        "zip_code": _text(addr, "zipCode"),
        "previous_names": [
            (e.text or "").strip()
            for e in (issuer.findall("issuerPreviousNameList/previousName") if issuer is not None else [])
            if (e.text or "").strip()
        ],
        # offering
        "industry_group": _text(offering, "industryGroup/industryGroupType"),
        "revenue_range": _text(offering, "issuerSize/revenueRange")
        or _text(offering, "issuerSize/aggregateNetAssetValueRange"),
        "federal_exemptions": [
            (e.text or "").strip()
            for e in (offering.findall("federalExemptionsExclusions/item") if offering is not None else [])
            if (e.text or "").strip()
        ],
        "date_of_first_sale": _text(offering, "typeOfFiling/dateOfFirstSale/value"),
        "yet_to_occur": _bool(offering, "typeOfFiling/dateOfFirstSale/yetToOccur"),
        "more_than_one_year": _bool(offering, "durationOfOffering/moreThanOneYear"),
        "security_types": _security_types(offering),
        "is_business_combination": _bool(
            offering, "businessCombinationTransaction/isBusinessCombinationTransaction"
        ),
        "minimum_investment": _money(offering, "minimumInvestmentAccepted")[0],
        "total_offering_amount": offer_amt,
        "is_indefinite": offer_indef,
        "total_amount_sold": _money(offering, "offeringSalesAmounts/totalAmountSold")[0],
        "total_remaining": _money(offering, "offeringSalesAmounts/totalRemaining")[0],
        "has_non_accredited": _bool(offering, "investors/hasNonAccreditedInvestors"),
        "num_investors": _int(offering, "investors/totalNumberAlreadyInvested"),
        "sales_commissions": _money(
            offering, "salesCommissionsFindersFees/salesCommissions/dollarAmount"
        )[0],
        "finders_fees": _money(
            offering, "salesCommissionsFindersFees/findersFees/dollarAmount"
        )[0],
        "use_of_proceeds": _money(
            offering, "useOfProceeds/grossProceedsUsed/dollarAmount"
        )[0],
        # children
        "related_persons": _related_persons(root),
        "recipients": _recipients(offering),
    }
    return rec


def _int(node, path: str):
    v = _text(node, path)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _security_types(offering) -> list[str]:
    if offering is None:
        return []
    node = offering.find("typesOfSecuritiesOffered")
    if node is None:
        return []
    return [label for tag, label in _SECURITY_TYPES.items() if _bool(node, tag)]


def _related_persons(root) -> list[dict]:
    people = []
    for p in root.findall("relatedPersonsList/relatedPersonInfo"):
        name_node = p.find("relatedPersonName")
        first = _text(name_node, "firstName") or ""
        middle = _text(name_node, "middleName") or ""
        last = _text(name_node, "lastName") or ""
        full = " ".join(x for x in (first, middle, last) if x)
        a = p.find("relatedPersonAddress")
        people.append(
            {
                "full_name": full,
                "relationships": [
                    (r.text or "").strip()
                    for r in p.findall("relatedPersonRelationshipList/relationship")
                    if (r.text or "").strip()
                ],
                "city": _text(a, "city"),
                "state": _text(a, "stateOrCountry"),
            }
        )
    return people


def _recipients(offering) -> list[dict]:
    if offering is None:
        return []
    out = []
    for r in offering.findall("salesCompensationList/recipient"):
        out.append(
            {
                "recipient_name": _text(r, "recipientName"),
                "crd_number": _text(r, "recipientCRDNumber"),
                "states_solicited": [
                    (s.text or "").strip()
                    for s in r.findall("statesOfSolicitationList/state")
                    if (s.text or "").strip()
                ],
            }
        )
    return out
