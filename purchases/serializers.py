from rest_framework import serializers

from purchases.models import PurchaseProposal, PurchaseProposalItem


class PurchaseProposalItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseProposalItem
        fields = [
            "id",
            "product_name",
            "strength",
            "company",
            "ware_house_name",
            "proposed_quantity",
            "unit_price",
            "line_total",
        ]


class PurchaseProposalSerializer(serializers.ModelSerializer):
    items = PurchaseProposalItemSerializer(many=True, read_only=True)
    created_by = serializers.StringRelatedField()
    approved_by = serializers.StringRelatedField()

    class Meta:
        model = PurchaseProposal
        fields = [
            "id",
            "status",
            "total_cost",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
            "items",
        ]


class PurchaseProposalStatusSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField()
    approved_by = serializers.StringRelatedField()

    class Meta:
        model = PurchaseProposal
        fields = [
            "id",
            "status",
            "total_cost",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]


class OCRResultIdsSerializer(serializers.Serializer):
    ocr_result_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        allow_empty=False,
        error_messages={"min_length": "At least one OCR result ID is required."},
    )


# ── Compare endpoint output ────────────────────────────────────────────────────

class OfferCandidateSerializer(serializers.Serializer):
    offer_id = serializers.IntegerField()
    ware_house_name = serializers.CharField(allow_null=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    item_id = serializers.IntegerField()


class DrugComparisonSerializer(serializers.Serializer):
    drug_key = serializers.CharField()
    drug_name = serializers.CharField()
    company = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=["found", "not_found"])
    best = OfferCandidateSerializer(allow_null=True)
    alternatives = OfferCandidateSerializer(many=True)
