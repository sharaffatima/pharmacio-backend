from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import Inventory
from rbac.models import AuditLog, Permission, Role, UserRole


class InventoryListApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username="inventory-user",
            email="inventory@example.com",
            password="pass1234",
        )
        self.client.force_authenticate(user=self.user)

    def test_inventory_list_requires_authentication(self):
        response = APIClient().get("/api/v1/inventory")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inventory_list_returns_paginated_results(self):
        for i in range(21):
            Inventory.objects.create(
                product_name=f"Product {i}",
                strength="500mg",
                quantity_on_hand=50,
                min_threshold=10,
            )

        response = self.client.get("/api/v1/inventory")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 21)
        self.assertEqual(len(response.data["results"]), 20)

    def test_inventory_list_includes_low_stock_indicator(self):
        low_item = Inventory.objects.create(
            product_name="Amoxicillin",
            strength="500mg",
            quantity_on_hand=5,
            min_threshold=10,
        )
        ok_item = Inventory.objects.create(
            product_name="Ibuprofen",
            strength="400mg",
            quantity_on_hand=25,
            min_threshold=10,
        )

        response = self.client.get("/api/v1/inventory")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        result_by_product = {item["product"]: item for item in results}

        self.assertEqual(result_by_product[low_item.product_name]["quantity"], 5)
        self.assertEqual(result_by_product[low_item.product_name]["status"], "low")
        self.assertEqual(result_by_product[ok_item.product_name]["quantity"], 25)
        self.assertEqual(result_by_product[ok_item.product_name]["status"], "ok")


class InventoryAdjustApiTests(TestCase):
    URL = "/api/v1/inventory/{pk}/adjust/"

    def _url(self, pk):
        return self.URL.format(pk=pk)

    def _make_user(self, username, email, with_permission=False):
        User = get_user_model()
        user = User.objects.create_user(
            username=username, email=email, password="pass1234"
        )
        if with_permission:
            perm, _ = Permission.objects.get_or_create(
                code="adjust_inventory", defaults={"action": "update"}
            )
            role, _ = Role.objects.get_or_create(name="inventory_manager")
            role.permissions.add(perm)
            UserRole.objects.get_or_create(user=user, role=role)
        return user

    def setUp(self):
        self.item = Inventory.objects.create(
            product_name="Paracetamol",
            strength="500mg",
            quantity_on_hand=100,
            min_threshold=20,
        )
        self.permitted_user = self._make_user(
            "adj-user", "adj@example.com", with_permission=True
        )
        self.unpermitted_user = self._make_user(
            "no-perm-user", "noperm@example.com", with_permission=False
        )

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        resp = client.post(self._url(self.item.pk), {"adjustment": 10}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_permission_returns_403(self):
        client = APIClient()
        client.force_authenticate(user=self.unpermitted_user)
        resp = client.post(self._url(self.item.pk), {"adjustment": 10}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_positive_adjustment_updates_quantity(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)
        resp = client.post(
            self._url(self.item.pk),
            {"adjustment": 50, "reason": "restock"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_on_hand, 150)
        self.assertEqual(resp.data["quantity"], 150)
        self.assertEqual(resp.data["previous_quantity"], 100)
        self.assertEqual(resp.data["adjustment"], 50)

    def test_negative_adjustment_updates_quantity(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)
        resp = client.post(
            self._url(self.item.pk),
            {"adjustment": -30, "reason": "write-off"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_on_hand, 70)

    def test_adjustment_that_causes_negative_stock_rejected(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)
        resp = client.post(
            self._url(self.item.pk),
            {"adjustment": -200},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # quantity must be unchanged
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_on_hand, 100)

    def test_adjustment_to_exactly_zero_is_allowed(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)
        resp = client.post(
            self._url(self.item.pk),
            {"adjustment": -100},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_on_hand, 0)

    def test_unknown_item_returns_404(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)
        resp = client.post(self._url(99999), {"adjustment": 1}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_adjustment_writes_audit_log(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)
        client.post(
            self._url(self.item.pk),
            {"adjustment": 10, "reason": "audit test"},
            format="json",
        )
        log = AuditLog.objects.filter(
            action="inventory_adjusted",
            actor=self.permitted_user,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.metadata["adjustment"], 10)
        self.assertEqual(log.metadata["previous_quantity"], 100)
        self.assertEqual(log.metadata["new_quantity"], 110)
        self.assertEqual(log.metadata["reason"], "audit test")

    def test_missing_adjustment_field_returns_400(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)
        resp = client.post(self._url(self.item.pk), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class InventoryCreateApiTests(TestCase):
    URL = "/api/v1/inventory/"

    def _make_user(self, username, email, with_permission=False):
        User = get_user_model()
        user = User.objects.create_user(
            username=username, email=email, password="pass1234"
        )
        if with_permission:
            perm, _ = Permission.objects.get_or_create(
                code="create_inventory", defaults={"action": "create"}
            )
            role, _ = Role.objects.get_or_create(name="inventory_creator")
            role.permissions.add(perm)
            UserRole.objects.get_or_create(user=user, role=role)
        return user

    def setUp(self):
        self.permitted_user = self._make_user(
            "create-user", "create@example.com", with_permission=True
        )
        self.unpermitted_user = self._make_user(
            "no-create-user", "nocreate@example.com", with_permission=False
        )

    def _payload(self, **overrides):
        base = {
            "product_name": "Aspirin",
            "strength": "100mg",
            "quantity_on_hand": 50,
            "min_threshold": 10,
        }
        base.update(overrides)
        return base

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        resp = client.post(self.URL, self._payload(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_permission_returns_403(self):
        client = APIClient()
        client.force_authenticate(user=self.unpermitted_user)
        resp = client.post(self.URL, self._payload(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_returns_201_with_correct_fields(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)
        resp = client.post(self.URL, self._payload(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["product"], "Aspirin")
        self.assertEqual(resp.data["quantity"], 50)
        self.assertEqual(resp.data["status"], "ok")
        self.assertTrue(Inventory.objects.filter(product_name="Aspirin").exists())

    def test_low_stock_status_on_create(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)
        resp = client.post(
            self.URL,
            self._payload(quantity_on_hand=5, min_threshold=10),
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "low")

    def test_missing_required_field_returns_400(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)
        resp = client.post(self.URL, {"product_name": "Aspirin"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_quantity_returns_400(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)
        resp = client.post(
            self.URL, self._payload(quantity_on_hand=-5), format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_product_and_strength_returns_400(self):
        Inventory.objects.create(
            product_name="Aspirin",
            strength="100mg",
            quantity_on_hand=20,
            min_threshold=5,
        )

        client = APIClient()
        client.force_authenticate(user=self.permitted_user)
        resp = client.post(self.URL, self._payload(), format="json")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Inventory.objects.filter(product_name="Aspirin", strength="100mg").count(), 1)

    def test_create_writes_audit_log(self):
        client = APIClient()
        client.force_authenticate(user=self.permitted_user)
        client.post(self.URL, self._payload(), format="json")
        log = AuditLog.objects.filter(
            action="inventory_item_created",
            actor=self.permitted_user,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.metadata["product_name"], "Aspirin")
        self.assertEqual(log.metadata["quantity_on_hand"], 50)
