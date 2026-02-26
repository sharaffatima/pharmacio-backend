from django.contrib import admin
from .models import OCRResultItem, OCRResults
# Register your models here.

admin.site.register(OCRResults)
admin.site.register(OCRResultItem)