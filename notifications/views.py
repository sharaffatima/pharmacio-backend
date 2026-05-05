from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import UserNotification, StockAlertRecord
from notifications.serializers import UserNotificationSerializer
from inventory.models import Inventory
from purchases.models import PurchaseProposal
from rbac.models import AuditLog


def _to_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes"}


class MyNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread_only = _to_bool(request.query_params.get("unread_only"))
        limit_raw = request.query_params.get("limit", "20")
        try:
            limit = max(1, min(int(limit_raw), 100))
        except ValueError:
            return Response(
                {"detail": "limit must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = UserNotification.objects.filter(user=request.user).select_related(
            "notification"
        )
        if unread_only:
            queryset = queryset.filter(is_read=False)

        queryset = queryset.order_by("-notification__created_at", "-id")
        unread_count = UserNotification.objects.filter(
            user=request.user,
            is_read=False,
        ).count()

        results = queryset[:limit]
        return Response(
            {
                "count": queryset.count(),
                "unread_count": unread_count,
                "results": UserNotificationSerializer(results, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_notification_id: int):
        try:
            entry = UserNotification.objects.select_related("notification").get(
                id=user_notification_id,
                user=request.user,
            )
        except UserNotification.DoesNotExist:
            return Response(
                {"detail": "Notification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not entry.is_read:
            entry.is_read = True
            entry.read_at = timezone.now()
            entry.save(update_fields=["is_read", "read_at", "updated_at"])

        return Response(
            UserNotificationSerializer(entry).data,
            status=status.HTTP_200_OK,
        )


class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        activity_alerts = UserNotification.objects.filter(
            user=request.user,
            is_read=False,
        ).count()

        low_stock = StockAlertRecord.objects.filter(
            is_below_threshold=True,
        ).count()

        proposals = PurchaseProposal.objects.filter(
            status="pending",
        ).count()

        inventory = Inventory.objects.count()

        return Response(
            {
                "activity_alerts": activity_alerts,
                "low_stock": low_stock,
                "proposals": proposals,
                "inventory": inventory,
            },
            status=status.HTTP_200_OK,
        )


ACTION_MESSAGES = {
    "proposal_generated": {"msg": "New proposal generated", "theme": "blue", "icon": "document"},
    "proposal_approved": {"msg": "Proposal approved", "theme": "green", "icon": "check"},
    "proposal_rejected": {"msg": "Proposal rejected", "theme": "red", "icon": "close"},
    "inventory_adjusted": {"msg": "Inventory adjusted", "theme": "blue", "icon": "box"},
    "inventory_item_created": {"msg": "New inventory item created", "theme": "green", "icon": "box"},
    "sale_recorded": {"msg": "POS transaction recorded", "theme": "green", "icon": "cash"},
    "refund_processed": {"msg": "POS refund processed", "theme": "green", "icon": "cash"},
    "assign_role": {"msg": "Role assigned", "theme": "blue", "icon": "shield"},
    "revoke_role": {"msg": "Role revoked", "theme": "red", "icon": "shield"},
    "create_permission": {"msg": "Permission created", "theme": "green", "icon": "key"},
    "delete_permission": {"msg": "Permission deleted", "theme": "red", "icon": "key"},
    "user_registered": {"msg": "New user registered", "theme": "green", "icon": "user"},
    "admin_created": {"msg": "Admin user created", "theme": "green", "icon": "shield"},
    "password_changed": {"msg": "Password changed", "theme": "blue", "icon": "key"},
    "file_uploaded": {"msg": "File uploaded", "theme": "blue", "icon": "upload"},
}

class RecentActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit_raw = request.query_params.get("limit", "10")
        try:
            limit = max(1, min(int(limit_raw), 50))
        except ValueError:
            limit = 10

        logs = AuditLog.objects.select_related("actor").order_by("-created_at")[:limit]

        results = []
        for log in logs:
            meta = ACTION_MESSAGES.get(log.action, {"msg": f"System action: {log.action}", "theme": "gray", "icon": "info"})
            results.append(
                {
                    "id": log.id,
                    "action": log.action,
                    "message": meta["msg"],
                    "theme": meta["theme"],
                    "icon": meta["icon"],
                    "created_at": log.created_at,
                    "actor": log.actor.username if log.actor else "System",
                }
            )

        return Response(results, status=status.HTTP_200_OK)
