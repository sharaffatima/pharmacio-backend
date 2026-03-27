from decimal import Decimal

from django.db import transaction

from ai_integration.services.comparison import compare_offers
from purchases.models import PurchaseProposal, PurchaseProposalItem


def generate_proposal(ocr_result_ids: list, created_by) -> PurchaseProposal:
    """
    Run best-price comparison across the given OCRResult IDs and persist a
    PurchaseProposal with one PurchaseProposalItem per found drug.

    Each item gets proposed_quantity=1 and line_total = unit_price * 1.

    Raises:
        ValueError: when no comparable items are found.
    """
    comparisons = compare_offers(ocr_result_ids)
    found = [c for c in comparisons if c.status == "found"]

    if not found:
        raise ValueError(
            "No comparable items found in the provided OCR results."
        )

    with transaction.atomic():
        total_cost = sum(c.best.price for c in found)

        proposal = PurchaseProposal.objects.create(
            created_by=created_by,
            total_cost=total_cost,
            status="pending",
        )

        items = []
        for comp in found:
            unit_price = comp.best.price
            proposed_quantity = 1
            line_total = unit_price * proposed_quantity
            items.append(
                PurchaseProposalItem(
                    proposal=proposal,
                    product_name=comp.drug_name,
                    company=comp.company,
                    ware_house_name=comp.best.ware_house_name,
                    proposed_quantity=proposed_quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )

        PurchaseProposalItem.objects.bulk_create(items)

    return proposal
