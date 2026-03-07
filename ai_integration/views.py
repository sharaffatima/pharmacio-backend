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

        try:
            job = OCRJob.objects.select_related("file").get(job_id=job_uuid)
        except OCRJob.DoesNotExist:
            return Response({"detail": "Unknown job_id"}, status=status.HTTP_400_BAD_REQUEST)

        # Create OCRResults row
        result = OCRResults.objects.create(
            job=job,
            file=job.file,
            ware_house_name=job.file.ware_house_name,
            confidence_score=_overall_confidence(payload),
            review_required=_review_required(payload),
            status="completed",
        )

        # Create items
        for item in payload.get("items", []):
            OCRResultItem.objects.create(
                ocr_result=result,
                extracted_product_name=item.get("drug_name", ""),
                extracted_strength=item.get("strength"),
                extracted_company=item.get("company"),
                extracted_quantity=1,
                extracted_unit_price=item.get("price", 0) or 0,
            )

        # Update job status to completed
        job.status = "ocr_done"
        job.error_message = None
        job.save(update_fields=["status", "error_message", "updated_at"])

        return Response({"detail": "Result received"}, status=200)


def _overall_confidence(payload: dict) -> float:
    items = payload.get("items") or []
    if not items:
        return 0.0
    vals = [float(i.get("confidence", 0.0) or 0.0) for i in items]
    # keep within [0,1]
    avg = sum(vals) / max(len(vals), 1)
    return max(0.0, min(1.0, avg))


def _review_required(payload: dict) -> bool:
    items = payload.get("items") or []
    # review_required true if any item requests review
    return any(bool(i.get("review_required")) for i in items)


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