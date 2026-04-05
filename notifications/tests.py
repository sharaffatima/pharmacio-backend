from django.test import TestCase
from django.db import connection
from unittest import skipUnless
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import Inventory
from notifications.models import (
	NotificationLog,
	NotificationLogEvent,
	NotificationType,
	Notification,
	StockAlertRecord,
)


@skipUnless(connection.vendor == "postgresql", "Postgres trigger test only")
class PostgresThresholdTriggerTests(TestCase):

	def test_trigger_creates_notification_and_recovery_log(self):
		item = Inventory.objects.create(
			product_name="Amoxicillin",
			strength="500mg",
			quantity_on_hand=3,
			min_threshold=10,
		)

		self.assertEqual(Notification.objects.count(), 1)
		self.assertEqual(NotificationLog.objects.count(), 1)
		self.assertEqual(item.stock_alert_record.logs.count(), 1)

		notif = Notification.objects.first()
		self.assertEqual(notif.type, NotificationType.LOW_STOCK)

		record = StockAlertRecord.objects.get(inventory=item)
		self.assertTrue(record.is_below_threshold)
		self.assertEqual(record.last_notified_quantity, 3)

		low_log = NotificationLog.objects.first()
		self.assertEqual(low_log.event, NotificationLogEvent.LOW_STOCK_DETECTED)
		self.assertEqual(low_log.created_notifications, 1)

		item.quantity_on_hand = 20
		item.save(update_fields=["quantity_on_hand", "updated_at"])

		self.assertEqual(Notification.objects.count(), 1)
		self.assertEqual(NotificationLog.objects.count(), 2)

		record.refresh_from_db()
		self.assertFalse(record.is_below_threshold)

		recovered_log = NotificationLog.objects.order_by("id").last()
		self.assertEqual(recovered_log.event, NotificationLogEvent.STOCK_RECOVERED)
		self.assertEqual(recovered_log.created_notifications, 0)


class NotificationInboxApiTests(TestCase):
	def setUp(self):
		self.user_model = get_user_model()
		self.user = self.user_model.objects.create_user(
			username="notif_user",
			password="password123",
			role="pharmacist",
		)
		self.other_user = self.user_model.objects.create_user(
			username="other_user",
			password="password123",
			role="admin",
		)

		self.notification = Notification.objects.create(
			message="Low stock alert: test",
			type=NotificationType.LOW_STOCK,
		)
		from notifications.models import UserNotification

		self.entry = UserNotification.objects.create(
			notification=self.notification,
			user=self.user,
		)
		self.other_entry = UserNotification.objects.create(
			notification=self.notification,
			user=self.other_user,
		)

	def test_user_can_list_own_notifications(self):
		client = APIClient()
		client.force_authenticate(self.user)

		response = client.get("/api/v1/notifications/me/?unread_only=true")

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["count"], 1)
		self.assertEqual(response.data["unread_count"], 1)
		self.assertEqual(len(response.data["results"]), 1)
		self.assertEqual(response.data["results"][0]["id"], self.entry.id)

	def test_user_can_mark_own_notification_as_read(self):
		client = APIClient()
		client.force_authenticate(self.user)

		response = client.post(f"/api/v1/notifications/{self.entry.id}/read/")

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.entry.refresh_from_db()
		self.assertTrue(self.entry.is_read)
		self.assertIsNotNone(self.entry.read_at)

	def test_user_cannot_mark_other_users_notification(self):
		client = APIClient()
		client.force_authenticate(self.user)

		response = client.post(f"/api/v1/notifications/{self.other_entry.id}/read/")

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class DashboardStatsApiTests(TestCase):
	def setUp(self):
		self.user_model = get_user_model()
		self.user = self.user_model.objects.create_user(
			username="stats_user",
			password="password123",
			role="pharmacist",
		)
		
		# Setup some test data
		from notifications.models import NotificationType, Notification, UserNotification, StockAlertRecord
		from django.db import connection
		
		if connection.vendor != "postgresql":
			notif = Notification.objects.create(message="Test", type=NotificationType.LOW_STOCK)
			UserNotification.objects.create(notification=notif, user=self.user, is_read=False)
		
		from inventory.models import Inventory
		item = Inventory.objects.create(product_name="P1", strength="10mg", quantity_on_hand=5, min_threshold=10)
		# Update stock_alert_record because the Postgres trigger might do it but here we're using sqlite maybe or we just explicitly set it
		if hasattr(item, 'stock_alert_record'):
			item.stock_alert_record.is_below_threshold = True
			item.stock_alert_record.save()
		else:
			StockAlertRecord.objects.create(inventory=item, is_below_threshold=True)
			
		from purchases.models import PurchaseProposal
		PurchaseProposal.objects.create(total_cost=100.0, created_by=self.user, status="pending")
		
	def test_get_dashboard_stats(self):
		client = APIClient()
		client.force_authenticate(self.user)

		response = client.get("/api/v1/notifications/dashboard/stats/")

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["activity_alerts"], 1)
		self.assertEqual(response.data["low_stock"], 1)
		self.assertEqual(response.data["proposals"], 1)
		self.assertEqual(response.data["inventory"], 1)


class RecentActivityApiTests(TestCase):
	def setUp(self):
		self.user_model = get_user_model()
		self.user = self.user_model.objects.create_user(
			username="activity_user",
			password="password123",
			role="pharmacist",
		)
		
		from rbac.models import AuditLog
		import datetime
		from django.utils import timezone
		
		# Create some audit logs
		AuditLog.objects.create(actor=self.user, action="proposal_generated")
		AuditLog.objects.create(actor=self.user, action="inventory_adjusted")
		AuditLog.objects.create(actor=None, action="file_uploaded")

	def test_get_recent_activity(self):
		client = APIClient()
		client.force_authenticate(self.user)

		response = client.get("/api/v1/notifications/dashboard/recent-activity/?limit=2")

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data), 2)
		self.assertEqual(response.data[0]["action"], "file_uploaded")
		self.assertEqual(response.data[0]["message"], "File uploaded")
		self.assertEqual(response.data[0]["actor"], "System")

		self.assertEqual(response.data[1]["action"], "inventory_adjusted")
		self.assertEqual(response.data[1]["actor"], "activity_user")
