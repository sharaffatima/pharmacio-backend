from django.urls import path

from notifications.views import MyNotificationsView, MarkNotificationReadView


urlpatterns = [
    path("notifications/me/", MyNotificationsView.as_view(), name="notifications-me"),
    path(
        "notifications/<int:user_notification_id>/read/",
        MarkNotificationReadView.as_view(),
        name="notifications-mark-read",
    ),
]
