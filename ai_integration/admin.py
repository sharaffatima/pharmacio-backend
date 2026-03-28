from django.contrib import admin
from .models import OCRResultItem, OCRResult
from .models import OCRJob
# Register your models here.

admin.site.register(OCRResult)
admin.site.register(OCRResultItem)
admin.site.register(OCRJob)