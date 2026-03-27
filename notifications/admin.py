from django.contrib import admin
from .models import NotificationLog, Notifications, StockAlertRecord, UserNotification
# Register your models here.

admin.site.register(Notifications)
admin.site.register(StockAlertRecord)
admin.site.register(NotificationLog)
admin.site.register(UserNotification)