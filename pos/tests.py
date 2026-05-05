from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import Inventory
from rbac.models import AuditLog, Permission, Role, UserRole
from pos.models import Transaction, TransactionItem, Payment


class POSCheckoutApiTests(TestCase):
    URL = "/api/v1/pos/checkout/"

    def _make_user(self, username, email, with_permission=False):
        user = get_user_model().objects.create_user(
            username=username,
            email=email,
            password="pass1234",
        )
        if with_permission:
            permission, _ = Permission.objects.get_or_create(
                code="record_sale", defaults={"action": "create"}
            )
            role, _ = Role.objects.get_or_create(name="cashier")
            role.permissions.add(permission)
            UserRole.objects.get_or_create(user=user, role=role)
        return user

    def setUp(self):
        self.inventory_item = Inventory.objects.create(
            product_name="Paracetamol",
            strength="500mg",
            quantity_on_hand=100,
            min_threshold=20,
        )
        self.permitted_user = self._make_user(
            "pos-user",
            "pos@example.com",
            with_permission=True,
        )
        self.unpermitted_user = self._make_user(
            "no-pos-user",
            "nopos@example.com",
            with_permission=False,
        )

        self.valid_payload = {
            "items": [
                {
                    "inventory_id": self.inventory_item.pk,
                    "quantity": 3,
                    "unit_price": "5.00",
                    "discount_percentage": "0.00"
                }
            ],
            "payments": [
                {
                    "payment_method": "cash",
                    "amount_paid": "15.00"
                }
            ],
            "discount_percentage": "0.00"
        }

    def test_unauthenticated_returns_401(self):
        response = APIClient().post(
            self.URL,
            self.valid_payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_permission_returns_403(self):
        client = APIClient()
        client.force_authenticate(user=self.unpermitted_user)

        response = client.post(
            self.URL,
            self.valid_payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_checkout_is_stored_and_inventory_reduced(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)

        response = client.post(
            self.URL,
            self.valid_payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.inventory_item.refresh_from_db()

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.total_amount, Decimal("15.00"))
        self.assertEqual(transaction.items.count(), 1)
        
        item = transaction.items.first()
        self.assertEqual(item.inventory_item.product_name, "Paracetamol")
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.unit_price, Decimal("5.00"))
        
        self.assertEqual(self.inventory_item.quantity_on_hand, 97)

    def test_insufficient_stock_returns_400_without_creating_transaction(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)

        payload = self.valid_payload.copy()
        payload["items"][0]["quantity"] = 200

        response = client.post(
            self.URL,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.inventory_item.refresh_from_db()
        self.assertEqual(self.inventory_item.quantity_on_hand, 100)
        self.assertFalse(Transaction.objects.exists())

    def test_unknown_inventory_returns_400(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)

        payload = self.valid_payload.copy()
        payload["items"][0]["inventory_id"] = 999999

        response = client.post(
            self.URL,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_checkout_writes_audit_log(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)

        client.post(
            self.URL,
            self.valid_payload,
            format="json",
        )

        audit_log = AuditLog.objects.filter(
            action="sale_recorded",
            actor=self.permitted_user,
        ).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.metadata["total"], "15.00")
