from rest_framework import serializers
from decimal import Decimal


class OCRPayloadItemSerializer(serializers.Serializer):
    """Validates a single extracted item from OCR payload."""
    drug_name = serializers.CharField(max_length=255)
    company = serializers.CharField(max_length=255, allow_blank=True, allow_null=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    confidence = serializers.FloatField(min_value=0.0, max_value=1.0)
    review_required = serializers.BooleanField()


class OCRPayloadSerializer(serializers.Serializer):
    """Validates the payload structure from OCR engine."""
    items = OCRPayloadItemSerializer(many=True)

    def validate_items(self, value):
        """Ensure at least one item is present."""
        if not value:
            raise serializers.ValidationError("'items' must contain at least one item")
        return value


class OCRResultSerializer(serializers.Serializer):
    """Validates the complete callback request from OCR engine."""
    job_id = serializers.UUIDField()
    payload = OCRPayloadSerializer()