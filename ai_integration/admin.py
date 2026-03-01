from django.contrib import admin
from .models import OCRResultItem, OCRResults
from .models import OCRJob
# Register your models here.

admin.site.register(OCRResults)
admin.site.register(OCRResultItem)
admin.site.register(OCRJob)