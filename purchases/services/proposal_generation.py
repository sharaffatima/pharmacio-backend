from decimal import Decimal

from django.db import transaction

from ai_integration.services.comparison import compare_offers
from purchases.models import PurchaseProposal, PurchaseProposalItem
from rbac.services.audit import create_audit_log


from typing import List
from collections import defaultdict

def generate_proposal(ocr_result_ids: list, created_by) -> List[PurchaseProposal]:
    """
    Run best-price comparison across the given OCRResult IDs and persist a
    PurchaseProposal per supplier (warehouse_name) with one PurchaseProposalItem per found drug.

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

    proposals = []
    
    # Group items by warehouse_name
    grouped_items = defaultdict(list)
    for comp in found:
        supplier_name = comp.best.ware_house_name or "Unknown Supplier"
        grouped_items[supplier_name].append(comp)

    with transaction.atomic():
        for supplier_name, comps in grouped_items.items():
            total_cost = sum(c.best.price for c in comps)

            proposal = PurchaseProposal.objects.create(
                created_by=created_by,
                total_cost=total_cost,
                status="pending",
            )

            items = []
            for comp in comps:
                unit_price = comp.best.price
                proposed_quantity = 1
                line_total = unit_price * proposed_quantity
                items.append(
                    PurchaseProposalItem(
                        proposal=proposal,
                        product_name=comp.drug_name,
                        company=comp.company,
                        ware_house_name=supplier_name,
                        proposed_quantity=proposed_quantity,
                        unit_price=unit_price,
                        line_total=line_total,
                    )
                )

            PurchaseProposalItem.objects.bulk_create(items)

            create_audit_log(
                actor=created_by,
                action="proposal_generated",
                entity=proposal,
                metadata={
                    "proposal_id": proposal.pk,
                    "supplier_name": supplier_name,
                    "total_cost": str(proposal.total_cost),
                    "items_count": len(items),
                },
            )
            
            proposals.append(proposal)

    return proposals
