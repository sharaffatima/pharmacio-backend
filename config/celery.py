import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("pharmacio")

# Load settings from Django settings.py where keys start with CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in installed apps
app.autodiscover_tasks()