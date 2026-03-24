from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from ai_integration.models import OCRResultItem


def _normalize(s: Optional[str]) -> str:
    """Lowercase, strip, collapse internal whitespace."""
    if not s:
        return ""
    return " ".join(s.lower().strip().split())


def make_drug_key(drug_name: str, company: Optional[str]) -> str:
    """Stable grouping key: '<normalized_name>|<normalized_company>'."""
    return f"{_normalize(drug_name)}|{_normalize(company)}"


@dataclass
class OfferCandidate:
    offer_id: int
    ware_house_name: Optional[str]
    price: Decimal
    item_id: int


@dataclass
class DrugComparison:
    drug_key: str
    drug_name: str
    company: Optional[str]
    status: str          # "found" | "not_found"
    best: Optional[OfferCandidate]
    alternatives: list = field(default_factory=list)  # list[OfferCandidate], sorted


def _sort_key(c: OfferCandidate):
    """Deterministic: price asc → warehouse name asc → item id asc."""
    return (c.price, c.ware_house_name or "", c.item_id)


def compare_offers(
    ocr_result_ids: list,
    requested_drug_keys: Optional[set] = None,
) -> list:
    """
    Compare OCRResultItems across the given OCRResults to find the cheapest
    available offer for each drug key.

    Args:
        ocr_result_ids:     PKs of OCRResults to compare.
        requested_drug_keys: Optional set of drug_key strings that must appear
                             in output even when absent from all offers.

    Returns:
        List of DrugComparison sorted by (found first, then drug_key alpha).
    """
    items = (
        OCRResultItem.objects
        .filter(ocr_result_id__in=ocr_result_ids)
        .select_related("ocr_result")
    )

    groups: dict[str, list[OfferCandidate]] = {}
    display: dict[str, tuple] = {}  # key -> (drug_name, company)

    for item in items:
        key = make_drug_key(item.extracted_product_name, item.extracted_company)
        candidate = OfferCandidate(
            offer_id=item.ocr_result_id,
            ware_house_name=item.ocr_result.ware_house_name,
            price=item.extracted_unit_price,
            item_id=item.id,
        )
        groups.setdefault(key, []).append(candidate)
        display.setdefault(key, (item.extracted_product_name, item.extracted_company))

    results = []

    for key, candidates in groups.items():
        sorted_candidates = sorted(candidates, key=_sort_key)
        drug_name, company = display[key]
        results.append(DrugComparison(
            drug_key=key,
            drug_name=drug_name,
            company=company,
            status="found",
            best=sorted_candidates[0],
            alternatives=sorted_candidates[1:],
        ))

    if requested_drug_keys:
        for key in sorted(requested_drug_keys - set(groups.keys())):
            parts = key.split("|", 1)
            results.append(DrugComparison(
                drug_key=key,
                drug_name=parts[0],
                company=parts[1] if len(parts) > 1 and parts[1] else None,
                status="not_found",
                best=None,
                alternatives=[],
            ))

    results.sort(key=lambda r: (0 if r.status == "found" else 1, r.drug_key))
    return results
