from rest_framework import serializers

from notifications.models import UserNotification


class UserNotificationSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="pk")
    notification_id = serializers.IntegerField()
    type = serializers.CharField(source="notification.type")
    message = serializers.CharField(source="notification.message")
    created_at = serializers.DateTimeField(source="notification.created_at")

    class Meta:
        model = UserNotification
        fields = [
            "id",
            "notification_id",
            "type",
            "message",
            "is_read",
            "read_at",
            "created_at",
        ]
