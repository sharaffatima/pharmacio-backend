from django.contrib import admin
from .models import NotificationLog, Notification, StockAlertRecord, UserNotification
# Register your models here.

admin.site.register(Notification)
admin.site.register(StockAlertRecord)
admin.site.register(NotificationLog)
admin.site.register(UserNotification)