from django.db import models

class Inventory(models.Model):
    product_name = models.CharField(max_length=255)
    strength = models.CharField(max_length=255)
    quantity_on_hand = models.IntegerField()
    min_threshold = models.IntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.product_name
    
    class Meta:
        indexes = [
            models.Index(fields=['product_name']),
            models.Index(fields=['strength']),
            models.Index(fields=['quantity_on_hand']),
            models.Index(fields=['min_threshold']),
            models.Index(fields=['updated_at']),
        ]
        constraints = [
        models.CheckConstraint(
            condition=models.Q(quantity_on_hand__gte=0),
            name="quantity_non_negative"
        )
    ]