from rest_framework import serializers

class OCRResultSerializer(serializers.Serializer):
    job_id = serializers.UUIDField()
    payload = serializers.JSONField()

    def validate_payload(self, value):
        required = ["schema_version", "created_at", "items"]
        for k in required:
            if k not in value:
                raise serializers.ValidationError(f"Missing '{k}'")

        if not isinstance(value["items"], list):
            raise serializers.ValidationError("'items' must be a list")

        for i, item in enumerate(value["items"]):
            for k in ["drug_name", "company", "strength", "price", "availability", "confidence", "review_required"]:
                if k not in item:
                    raise serializers.ValidationError(f"Item {i} missing '{k}'")

        return value