from django.urls import path

from notifications.views import MyNotificationsView, MarkNotificationReadView, DashboardStatsView, RecentActivityView


urlpatterns = [
    path("notifications/me/", MyNotificationsView.as_view(), name="notifications-me"),
    path(
        "notifications/<int:user_notification_id>/read/",
        MarkNotificationReadView.as_view(),
        name="notifications-mark-read",
    ),
    path("notifications/dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("notifications/dashboard/recent-activity/", RecentActivityView.as_view(), name="dashboard-recent-activity"),
]
