from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import UserNotification
from notifications.serializers import UserNotificationSerializer


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
