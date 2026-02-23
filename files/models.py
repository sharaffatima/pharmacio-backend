from django.db import models
# Create your models here.

class File(models.Model):
    s3_key = models.CharField(max_length=255, unique=True)
    original_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_filename
    
    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

