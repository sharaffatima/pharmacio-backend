from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import Inventory


class InventoryListApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username="inventory-user",
            email="inventory@example.com",
            password="pass1234",
        )
        self.client.force_authenticate(user=self.user)

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
