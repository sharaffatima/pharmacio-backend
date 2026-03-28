from django.db import models


class NotificationType(models.TextChoices):
    LOW_STOCK = "low_stock", "Low Stock"


class NotificationLogEvent(models.TextChoices):
    LOW_STOCK_DETECTED = "low_stock_detected", "Low Stock Detected"
    STOCK_RECOVERED = "stock_recovered", "Stock Recovered"


class Notification(models.Model):
    message = models.TextField()
    type = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    

    def __str__(self):
        return f"{self.type} - {self.message[:20]}..."

    class Meta:
        db_table = 'notifications_notifications'
        indexes = [
            models.Index(fields=['type']),
            models.Index(fields=['created_at']),
        ]


class StockAlertRecord(models.Model):
    inventory = models.OneToOneField(
        "inventory.Inventory",
        on_delete=models.CASCADE,
        related_name="stock_alert_record",
    )
    is_below_threshold = models.BooleanField(default=False)
    last_notified_at = models.DateTimeField(null=True, blank=True)
    last_notified_quantity = models.IntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_below_threshold"]),
            models.Index(fields=["updated_at"]),
        ]


class NotificationLog(models.Model):
    inventory = models.ForeignKey(
        "inventory.Inventory",
        on_delete=models.CASCADE,
        related_name="notification_logs",
    )
    record = models.ForeignKey(
        StockAlertRecord,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    event = models.CharField(max_length=64, choices=NotificationLogEvent.choices)
    message = models.TextField()
    created_notifications = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["event", "created_at"]),
            models.Index(fields=["inventory", "created_at"]),
        ]


class UserNotification(models.Model):
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name="user_notifications",
    )
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "user"],
                name="notification_user_unique",
            )
        ]
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"]),
            models.Index(fields=["notification", "user"]),
        ]