from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import Inventory
from rbac.models import AuditLog, Permission, Role, UserRole
from sales.models import Sale


class SalesCreateApiTests(TestCase):
	URL = "/api/v1/sales"

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
			"sales-user",
			"sales@example.com",
			with_permission=True,
		)
		self.unpermitted_user = self._make_user(
			"no-sales-user",
			"nosales@example.com",
			with_permission=False,
		)

	def test_unauthenticated_returns_401(self):
		response = APIClient().post(
			self.URL,
			{
				"inventory_id": self.inventory_item.pk,
				"quantity_sold": 2,
				"unit_price": "4.99",
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_missing_permission_returns_403(self):
		client = APIClient()
		client.force_authenticate(user=self.unpermitted_user)

		response = client.post(
			self.URL,
			{
				"inventory_id": self.inventory_item.pk,
				"quantity_sold": 2,
				"unit_price": "4.99",
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_sale_is_stored_and_inventory_reduced(self):
		client = APIClient()
		client.force_authenticate(user=self.permitted_user)

		response = client.post(
			self.URL,
			{
				"inventory_id": self.inventory_item.pk,
				"quantity_sold": 3,
				"unit_price": "4.99",
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.inventory_item.refresh_from_db()

		sale = Sale.objects.get()
		self.assertEqual(sale.product_name, "Paracetamol")
		self.assertEqual(sale.strength, "500mg")
		self.assertEqual(sale.quantity_sold, 3)
		self.assertEqual(sale.unit_price, Decimal("4.99"))
		self.assertEqual(self.inventory_item.quantity_on_hand, 97)
		self.assertEqual(response.data["remaining_quantity"], 97)

	def test_insufficient_stock_returns_400_without_creating_sale(self):
		client = APIClient()
		client.force_authenticate(user=self.permitted_user)

		response = client.post(
			self.URL,
			{
				"inventory_id": self.inventory_item.pk,
				"quantity_sold": 200,
				"unit_price": "4.99",
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.inventory_item.refresh_from_db()
		self.assertEqual(self.inventory_item.quantity_on_hand, 100)
		self.assertFalse(Sale.objects.exists())

	def test_unknown_inventory_returns_404(self):
		client = APIClient()
		client.force_authenticate(user=self.permitted_user)

		response = client.post(
			self.URL,
			{
				"inventory_id": 999999,
				"quantity_sold": 2,
				"unit_price": "4.99",
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

	def test_sale_writes_audit_log(self):
		client = APIClient()
		client.force_authenticate(user=self.permitted_user)

		client.post(
			self.URL,
			{
				"inventory_id": self.inventory_item.pk,
				"quantity_sold": 5,
				"unit_price": "2.50",
			},
			format="json",
		)

		audit_log = AuditLog.objects.filter(
			action="sale_recorded",
			actor=self.permitted_user,
		).first()
		self.assertIsNotNone(audit_log)
		self.assertEqual(audit_log.metadata["inventory_id"], self.inventory_item.pk)
		self.assertEqual(audit_log.metadata["quantity_sold"], 5)
		self.assertEqual(audit_log.metadata["remaining_quantity"], 95)
