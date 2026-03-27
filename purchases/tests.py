from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from ai_integration.models import OCRResultItem, OCRResults
from ai_integration.services.comparison import compare_offers, make_drug_key
from files.models import File
from purchases.models import PurchaseHistory, PurchaseProposal
from rbac.models import AuditLog, Permission, Role, UserRole
from purchases.services.proposal_generation import generate_proposal
from rbac.constants import APPROVE_PURCHASE_PROPOSAL
from users.models import User


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_user(username="testuser"):
    return User.objects.create_user(
        username=username, password="password123", email=f"{username}@example.com"
    )


def _make_file(user):
    return File.objects.create(
        s3_key=f"uploads/{user.username}/test.pdf",
        original_filename="test.pdf",
        status="uploaded",
    )


def _grant_permission(user, permission_code, action="update", role_name=None):
    permission, _ = Permission.objects.get_or_create(
        code=permission_code,
        defaults={"action": action},
    )
    role, _ = Role.objects.get_or_create(name=role_name or f"role_{permission_code}")
    role.permissions.add(permission)
    UserRole.objects.get_or_create(user=user, role=role)
    return permission


def _make_ocr_result(file, ware_house_name="WarehouseA"):
    return OCRResults.objects.create(
        file=file,
        ware_house_name=ware_house_name,
        confidence_score=0.9,
        review_required=False,
        status="completed",
    )


def _make_item(ocr_result, product_name, company=None, price="5.00"):
    return OCRResultItem.objects.create(
        ocr_result=ocr_result,
        extracted_product_name=product_name,
        extracted_company=company,
        extracted_unit_price=Decimal(price),
    )


# ── Comparison service tests ───────────────────────────────────────────────────

class CompareOffersServiceTest(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.file = _make_file(self.user)

    def test_best_price_selected(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        result_b = _make_ocr_result(self.file, "WarehouseB")
        _make_item(result_a, "Paracetamol", "PharmaA", "5.00")
        _make_item(result_b, "Paracetamol", "PharmaA", "3.50")

        comparisons = compare_offers([result_a.id, result_b.id])

        self.assertEqual(len(comparisons), 1)
        self.assertEqual(comparisons[0].status, "found")
        self.assertEqual(comparisons[0].best.price, Decimal("3.50"))
        self.assertEqual(comparisons[0].best.ware_house_name, "WarehouseB")

    def test_tie_break_is_deterministic(self):
        """Equal prices → warehouse name asc → item id asc."""
        result_a = _make_ocr_result(self.file, "Warehouse_Z")
        result_b = _make_ocr_result(self.file, "Warehouse_A")
        _make_item(result_a, "Ibuprofen", "PharmaX", "4.00")
        _make_item(result_b, "Ibuprofen", "PharmaX", "4.00")

        comparisons = compare_offers([result_a.id, result_b.id])

        self.assertEqual(len(comparisons), 1)
        self.assertEqual(comparisons[0].best.ware_house_name, "Warehouse_A")

    def test_missing_product_returns_not_found(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        _make_item(result_a, "Paracetamol", "PharmaA", "5.00")

        missing_key = make_drug_key("Amoxicillin", "PharmaB")
        comparisons = compare_offers([result_a.id], requested_drug_keys={missing_key})

        not_found = [c for c in comparisons if c.status == "not_found"]
        self.assertEqual(len(not_found), 1)
        self.assertIsNone(not_found[0].best)

    def test_multiple_products_grouped_correctly(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        _make_item(result_a, "Paracetamol", "PharmaA", "2.00")
        _make_item(result_a, "Ibuprofen", "PharmaA", "3.00")

        comparisons = compare_offers([result_a.id])

        self.assertEqual(len(comparisons), 2)
        names = {c.drug_name.lower() for c in comparisons}
        self.assertIn("paracetamol", names)
        self.assertIn("ibuprofen", names)

    def test_alternatives_contain_non_best_offers(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        result_b = _make_ocr_result(self.file, "WarehouseB")
        _make_item(result_a, "Paracetamol", "PharmaA", "5.00")
        _make_item(result_b, "Paracetamol", "PharmaA", "3.00")

        comparisons = compare_offers([result_a.id, result_b.id])

        self.assertEqual(len(comparisons[0].alternatives), 1)
        self.assertEqual(comparisons[0].alternatives[0].price, Decimal("5.00"))

    def test_empty_ocr_result_ids_returns_empty_list(self):
        comparisons = compare_offers([])
        self.assertEqual(comparisons, [])


# ── Proposal generation service tests ─────────────────────────────────────────

class ProposalGenerationServiceTest(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.file = _make_file(self.user)

    def test_proposal_total_is_correct(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        _make_item(result_a, "Paracetamol", "PharmaA", "2.50")
        _make_item(result_a, "Ibuprofen", "PharmaA", "3.75")

        proposal = generate_proposal([result_a.id], created_by=self.user)

        self.assertEqual(proposal.total_cost, Decimal("6.25"))
        self.assertEqual(proposal.items.count(), 2)

    def test_proposal_items_use_best_price(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        result_b = _make_ocr_result(self.file, "WarehouseB")
        _make_item(result_a, "Paracetamol", "PharmaA", "5.00")
        _make_item(result_b, "Paracetamol", "PharmaA", "2.00")

        proposal = generate_proposal([result_a.id, result_b.id], created_by=self.user)

        item = proposal.items.first()
        self.assertEqual(item.unit_price, Decimal("2.00"))
        self.assertEqual(item.line_total, Decimal("2.00"))

    def test_default_quantity_is_one(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        _make_item(result_a, "Amoxicillin", "PharmaA", "7.00")

        proposal = generate_proposal([result_a.id], created_by=self.user)

        self.assertEqual(proposal.items.first().proposed_quantity, 1)

    def test_no_items_raises_value_error(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        # No OCRResultItems → nothing to compare.
        with self.assertRaises(ValueError):
            generate_proposal([result_a.id], created_by=self.user)

    def test_proposal_status_defaults_to_pending(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        _make_item(result_a, "Paracetamol", "PharmaA", "2.50")

        proposal = generate_proposal([result_a.id], created_by=self.user)

        self.assertEqual(proposal.status, "pending")
        self.assertEqual(proposal.created_by, self.user)

    def test_line_total_equals_unit_price_times_quantity(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        _make_item(result_a, "Paracetamol", "PharmaA", "4.99")

        proposal = generate_proposal([result_a.id], created_by=self.user)
        item = proposal.items.first()

        self.assertEqual(item.line_total, item.unit_price * item.proposed_quantity)


# ── API endpoint tests ─────────────────────────────────────────────────────────

class PurchaseProposalAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = _make_user()
        self.approver = _make_user("approver")
        _grant_permission(
            self.approver,
            APPROVE_PURCHASE_PROPOSAL,
            action="update",
            role_name="purchase_approver",
        )
        self.client.force_authenticate(user=self.user)
        self.file = _make_file(self.user)

    # compare ──────────────────────────────────────────────────────────────────

    def test_compare_returns_best_price(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        result_b = _make_ocr_result(self.file, "WarehouseB")
        _make_item(result_a, "Paracetamol", "PharmaA", "5.00")
        _make_item(result_b, "Paracetamol", "PharmaA", "3.00")

        response = self.client.post(
            "/api/v1/purchase-proposals/compare",
            {"ocr_result_ids": [result_a.id, result_b.id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["best"]["price"], "3.00")
        self.assertEqual(data[0]["best"]["ware_house_name"], "WarehouseB")

    def test_compare_empty_ids_rejected(self):
        response = self.client.post(
            "/api/v1/purchase-proposals/compare",
            {"ocr_result_ids": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compare_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/v1/purchase-proposals/compare",
            {"ocr_result_ids": [1]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # generate ─────────────────────────────────────────────────────────────────

    def test_generate_creates_proposal(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        _make_item(result_a, "Paracetamol", "PharmaA", "2.50")

        response = self.client.post(
            "/api/v1/purchase-proposals/generate",
            {"ocr_result_ids": [result_a.id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["status"], "pending")
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["total_cost"], "2.50")

    def test_generate_with_no_items_returns_400(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")

        response = self.client.post(
            "/api/v1/purchase-proposals/generate",
            {"ocr_result_ids": [result_a.id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_generate_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/v1/purchase-proposals/generate",
            {"ocr_result_ids": [1]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # list ─────────────────────────────────────────────────────────────────────

    def test_list_returns_existing_proposals(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        _make_item(result_a, "Paracetamol", "PharmaA", "2.50")
        generate_proposal([result_a.id], created_by=self.user)

        response = self.client.get("/api/v1/purchase-proposals")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        proposals = body.get("results", body)
        self.assertEqual(len(proposals), 1)

    def test_list_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/purchase-proposals")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # detail ───────────────────────────────────────────────────────────────────

    def test_detail_returns_proposal(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        _make_item(result_a, "Paracetamol", "PharmaA", "2.50")
        proposal = generate_proposal([result_a.id], created_by=self.user)

        response = self.client.get(f"/api/v1/purchase-proposals/{proposal.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["id"], proposal.id)

    def test_detail_404_for_unknown_id(self):
        response = self.client.get("/api/v1/purchase-proposals/99999")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # approval workflow ───────────────────────────────────────────────────────

    def test_approve_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post("/api/v1/purchase-proposals/1/approve")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_approve_requires_permission(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        _make_item(result_a, "Paracetamol", "PharmaA", "2.50")
        proposal = generate_proposal([result_a.id], created_by=self.user)

        response = self.client.post(f"/api/v1/purchase-proposals/{proposal.id}/approve")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_approve_pending_proposal(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        _make_item(result_a, "Paracetamol", "PharmaA", "2.50")
        proposal = generate_proposal([result_a.id], created_by=self.user)
        self.client.force_authenticate(user=self.approver)

        response = self.client.post(f"/api/v1/purchase-proposals/{proposal.id}/approve")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "approved")
        self.assertEqual(proposal.approved_by, self.approver)

        history = PurchaseHistory.objects.filter(proposal=proposal).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.total_cost, proposal.total_cost)
        self.assertEqual(history.created_by, proposal.created_by)
        self.assertEqual(history.approved_by, self.approver)

        log = AuditLog.objects.filter(action="proposal_approved", actor=self.approver).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.metadata["proposal_id"], proposal.id)
        self.assertEqual(log.metadata["new_status"], "approved")

    def test_approve_non_pending_proposal_rejected(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        _make_item(result_a, "Paracetamol", "PharmaA", "2.50")
        proposal = generate_proposal([result_a.id], created_by=self.user)
        proposal.status = "rejected"
        proposal.save(update_fields=["status", "updated_at"])
        self.client.force_authenticate(user=self.approver)

        response = self.client.post(f"/api/v1/purchase-proposals/{proposal.id}/approve")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_pending_proposal(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        _make_item(result_a, "Paracetamol", "PharmaA", "2.50")
        proposal = generate_proposal([result_a.id], created_by=self.user)
        self.client.force_authenticate(user=self.approver)

        response = self.client.post(f"/api/v1/purchase-proposals/{proposal.id}/reject")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "rejected")
        self.assertEqual(proposal.approved_by, self.approver)
        self.assertFalse(PurchaseHistory.objects.filter(proposal=proposal).exists())

        log = AuditLog.objects.filter(action="proposal_rejected", actor=self.approver).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.metadata["proposal_id"], proposal.id)
        self.assertEqual(log.metadata["new_status"], "rejected")

    def test_reject_requires_permission(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        _make_item(result_a, "Paracetamol", "PharmaA", "2.50")
        proposal = generate_proposal([result_a.id], created_by=self.user)

        response = self.client.post(f"/api/v1/purchase-proposals/{proposal.id}/reject")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_status_endpoint_returns_current_status(self):
        result_a = _make_ocr_result(self.file, "WarehouseA")
        _make_item(result_a, "Paracetamol", "PharmaA", "2.50")
        proposal = generate_proposal([result_a.id], created_by=self.user)
        self.client.force_authenticate(user=self.approver)
        self.client.post(f"/api/v1/purchase-proposals/{proposal.id}/approve")

        response = self.client.get(f"/api/v1/purchase-proposals/{proposal.id}/status")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "approved")
        self.assertEqual(response.json()["approved_by"], str(self.approver))

    def test_status_endpoint_404_for_unknown_id(self):
        response = self.client.get("/api/v1/purchase-proposals/99999/status")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

