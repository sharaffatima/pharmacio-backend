from django.db import models
import uuid


class Notifications(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.TextField()
    type = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    

    def __str__(self):
        return f"{self.type} - {self.message[:20]}..."

    class Meta:
        indexes = [
            models.Index(fields=['type']),
            models.Index(fields=['created_at']),
        ]