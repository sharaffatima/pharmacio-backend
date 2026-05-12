from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import Inventory, InventoryBarcode
from rbac.models import AuditLog, Permission, Role, UserRole
from pos.models import Transaction, TransactionItem, Payment


class POSBarcodeLookupApiTests(TestCase):
    URL = "/api/v1/pos/barcode-lookup/"

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
            product_name="Aspirin",
            strength="100mg",
            quantity_on_hand=20,
            min_threshold=5,
        )
        self.barcode = InventoryBarcode.objects.create(
            inventory_item=self.inventory_item,
            barcode="4012345678901",
            is_primary=True,
        )
        self.permitted_user = self._make_user(
            "barcode-user",
            "barcode@example.com",
            with_permission=True,
        )
        self.unpermitted_user = self._make_user(
            "barcode-no-perm",
            "barcode-no-perm@example.com",
            with_permission=False,
        )

    def test_unauthenticated_returns_401(self):
        response = APIClient().get(self.URL, {"barcode": self.barcode.barcode})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_permission_returns_403(self):
        client = APIClient()
        client.force_authenticate(user=self.unpermitted_user)

        response = client.get(self.URL, {"barcode": self.barcode.barcode})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_barcode_returns_400(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)

        response = client.get(self.URL)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_barcode_returns_404(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)

        response = client.get(self.URL, {"barcode": "0000000000000"})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_lookup_returns_inventory_item_for_barcode(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)

        response = client.get(self.URL, {"barcode": self.barcode.barcode})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "barcode": "4012345678901",
                "inventory_id": self.inventory_item.id,
                "product_name": "Aspirin",
                "strength": "100mg",
                "quantity_on_hand": 20,
                "min_threshold": 5,
            },
        )

    def test_lookup_trims_scanned_barcode(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)

        response = client.get(self.URL, {"barcode": " 4012345678901 "})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["inventory_id"], self.inventory_item.id)


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

    def test_checkout_reduces_only_inventory_item_matching_id(self):
        other_item = Inventory.objects.create(
            product_name="Ibuprofen",
            strength="400mg",
            quantity_on_hand=40,
            min_threshold=10,
        )
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)

        payload = {
            "items": [
                {
                    "inventory_id": other_item.pk,
                    "quantity": 4,
                    "unit_price": "2.50",
                    "discount_percentage": "0.00",
                }
            ],
            "payments": [
                {
                    "payment_method": "cash",
                    "amount_paid": "10.00",
                }
            ],
            "discount_percentage": "0.00",
        }

        response = client.post(self.URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.inventory_item.refresh_from_db()
        other_item.refresh_from_db()

        self.assertEqual(self.inventory_item.quantity_on_hand, 100)
        self.assertEqual(other_item.quantity_on_hand, 36)
        transaction_item = TransactionItem.objects.get()
        self.assertEqual(transaction_item.inventory_item_id, other_item.pk)

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
