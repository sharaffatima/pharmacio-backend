"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.http import JsonResponse
from django.db import connection
import logging

logger = logging.getLogger(__name__)

def health(request):
    return JsonResponse({"status": "ok"})

def health_db(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        return JsonResponse({"status": "ok", "db": "ok"})
    except Exception as e:
        logger.exception("Health-check DB probe failed: %s", e)
        return JsonResponse({"status": "degraded", "db": "error"}, status=503)
    

urlpatterns = [
    path('admin/', admin.site.urls),
    path("health/", health),
    path("health/db/", health_db),
    path('api/v1/', include('users.urls')),
    path('api/v1/rbac/', include('rbac.urls')),
    path('api/v1/', include('files.urls')),
    path('api/v1/', include('ai_integration.urls')),
    path('api/v1/', include('inventory.urls')),
    path('api/v1/', include('sales.urls')),
    path('api/v1/', include('purchases.urls')),
    path('api/v1/', include('notifications.urls')),
]
