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
    payload = serializers.DictField()

    def validate_payload(self, value):
        # Accept legacy normalized payload.
        if "items" in value:
            nested = OCRPayloadSerializer(data=value)
            nested.is_valid(raise_exception=True)
            return nested.validated_data

        # Accept raw OCR engine table payloads like page_001_raw_steps.
        raw_step_keys = [k for k in value.keys() if k.endswith("_raw_steps")]
        if raw_step_keys:
            for key in raw_step_keys:
                rows = value.get(key)
                if not isinstance(rows, list):
                    raise serializers.ValidationError({key: "Must be a list of row objects."})
                for row in rows:
                    if not isinstance(row, dict):
                        raise serializers.ValidationError({key: "Each row must be an object."})
            return value

        raise serializers.ValidationError(
            "Payload must include either 'items' or at least one '*_raw_steps' list."
        )
    

# ── Frontend-facing serializers ────────────────────────────────────────────────

class AvailableOfferSerializer(serializers.ModelSerializer):
    file_id = serializers.UUIDField(source="file.id", read_only=True)
    original_filename = serializers.CharField(source="file.original_filename", read_only=True)
    items_count = serializers.IntegerField(read_only=True)

    class Meta:
        from ai_integration.models import OCRResult

        model = OCRResult
        fields = [
            "id",
            "file_id",
            "original_filename",
            "ware_house_name",
            "status",
            "confidence_score",
            "review_required",
            "created_at",
            "items_count",
        ]
