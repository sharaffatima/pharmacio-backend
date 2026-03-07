from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import uuid

from ai_integration.models import OCRJob, OCRResults, OCRResultItem
from ai_integration.serializers import OCRResultSerializer
from ai_integration.tasks import dispatch_ocr_job
from rest_framework.permissions import AllowAny, IsAuthenticated

class OCRResultCallbackView(APIView):
    """
    Callback endpoint for OCR engine to POST results.
    POST /ai/ocr/result/
    Payload: {job_id: UUID, payload: {...result data...}}
    """
    permission_classes = [AllowAny] # just for testing, should be more restrictive in production
    def post(self, request):
        serializer = OCRResultSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=422)

        job_uuid = serializer.validated_data["job_id"]
        payload = serializer.validated_data["payload"]

        with transaction.atomic():
            try:
                job = OCRJob.objects.select_related("file").select_for_update().get(job_id=job_uuid)
            except OCRJob.DoesNotExist:
                return Response({"detail": "Unknown job_id"}, status=status.HTTP_400_BAD_REQUEST)

            # Create OCRResults row with aggregated data
            result = OCRResults.objects.create(
                job=job,
                file=job.file,
                ware_house_name=job.file.ware_house_name,
                confidence_score=_calculate_overall_confidence(payload["items"]),
                review_required=_calculate_review_required(payload["items"]),
                status="completed",
            )

            # Create OCRResultItem for each extracted item
            for item in payload["items"]:
                OCRResultItem.objects.create(
                    ocr_result=result,
                    extracted_product_name=item["drug_name"],
                    extracted_company=item.get("company"),
                    extracted_unit_price=item["price"],
                )

            # Update job status to completed
            job.status = "ocr_done"
            job.error_message = None
            job.save(update_fields=["status", "error_message", "updated_at"])

        return Response({"detail": "Result received"}, status=200)


def _calculate_overall_confidence(items: list) -> float:
    """Calculate average confidence score from all extracted items."""
    if not items:
        return 0.0
    confidences = [float(item["confidence"]) for item in items]
    avg = sum(confidences) / len(confidences)
    # Ensure within [0, 1] range due to DB constraint
    return max(0.0, min(1.0, avg))


def _calculate_review_required(items: list) -> bool:
    """Return True if any item requires review."""
    return any(item["review_required"] for item in items)


class OCRJobStatusView(APIView):
    """
    Endpoint to check the status of an OCR job.
    GET /ai/ocr/job/{job_id}/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        job = get_object_or_404(OCRJob, job_id=job_id)
        
        return Response({
            "job_id": str(job.job_id),
            "file_id": str(job.file.id),
            "status": job.status,
            "retries": job.retries,
            "error_message": job.error_message,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }, status=status.HTTP_200_OK)


class ManualDispatchView(APIView):
    """
    Endpoint to manually trigger OCR dispatch for a job.
    Useful for recovery/retry scenarios.
    POST /ai/ocr/dispatch/{job_id}/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        job = get_object_or_404(OCRJob, job_id=job_id)
        
        # Reset job status and trigger dispatch
        job.status = "queued"
        job.retries = 0
        job.error_message = None
        job.save(update_fields=["status", "retries", "error_message", "updated_at"])
        
        # Trigger the dispatch task
        dispatch_ocr_job.delay(job.id)
        
        return Response({
            "detail": "Dispatch triggered",
            "job_id": str(job.job_id),
        }, status=status.HTTP_202_ACCEPTED)