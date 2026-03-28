import logging
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
import uuid
from rbac.services.audit import create_audit_log

logger = logging.getLogger(__name__)

from ai_integration.models import OCRJob, OCRResult, OCRResultItem
from ai_integration.serializers import OCRResultSerializer
from ai_integration.services.payload_normalization import normalize_ocr_payload_items
from ai_integration.tasks import dispatch_ocr_job


class InternalServiceAuthentication(BasePermission):
    """
    Custom permission to authenticate OCR engine callbacks using shared token.
    Checks Authorization header against INTERNAL_SERVICE_TOKEN.
    """
    def has_permission(self, request, view):
        auth_header = request.headers.get('Authorization', '')
        internal_token = getattr(settings, 'INTERNAL_SERVICE_TOKEN', '')

        if not internal_token:
            logger.error("INTERNAL_SERVICE_TOKEN is not configured – denying request")
            return False

        if auth_header == internal_token:
            logger.debug("OCR callback authenticated successfully")
            return True

        logger.warning("OCR callback authentication failed - invalid token")
        return False

class OCRResultCallbackView(APIView):
    """
    Callback endpoint for OCR engine to POST results.
    POST /api/v1/ocr/result/
    Payload: {job_id: UUID, payload: {...result data...}}
    Authentication: Requires INTERNAL_SERVICE_TOKEN in Authorization header
    """
    permission_classes = [InternalServiceAuthentication]
    
    def post(self, request):
        logger.info("Received OCR callback request")
        serializer = OCRResultSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"Invalid OCR callback payload: {serializer.errors}")
            return Response(serializer.errors, status=422)

        job_uuid = serializer.validated_data["job_id"]
        payload = serializer.validated_data["payload"]
        normalized_items = normalize_ocr_payload_items(payload)
        if not normalized_items:
            logger.warning(f"No parsable OCR items found for job_id={job_uuid}")
            return Response(
                {"detail": "OCR payload did not contain any parsable items."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        with transaction.atomic():
            try:
                job = OCRJob.objects.select_related("file").select_for_update().get(job_id=job_uuid)
                logger.info(f"Processing OCR results for job {job_uuid}, file={job.file.original_filename}")
            except OCRJob.DoesNotExist:
                logger.error(f"OCR callback received for unknown job_id: {job_uuid}")
                return Response({"detail": "Unknown job_id"}, status=status.HTTP_400_BAD_REQUEST)

            # Create OCRResult row with aggregated data
            result = OCRResult.objects.create(
                job=job,
                file=job.file,
                ware_house_name=job.file.ware_house_name,
                confidence_score=_calculate_overall_confidence(normalized_items),
                review_required=_calculate_review_required(normalized_items),
                status="completed",
            )

            # Create OCRResultItems in a single bulk INSERT
            OCRResultItem.objects.bulk_create([
                OCRResultItem(
                    ocr_result=result,
                    extracted_product_name=item["drug_name"],
                    extracted_company=item.get("company"),
                    extracted_unit_price=item["price"],
                )
                for item in normalized_items
            ])

            # Update job status to ocr_done
            job.status = "ocr_done"
            job.error_message = None
            job.save(update_fields=["status", "error_message", "updated_at"])
            
            # Sync File status to reflect processing completion
            job.file.status = "completed"
            job.file.save(update_fields=["status"])
            
            logger.info(f"Successfully processed OCR results for job {job_uuid}: {len(normalized_items)} items extracted")

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
    GET /api/v1/ocr/job/{job_id}/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        logger.debug(f"Job status request for job_id={job_id} by user={request.user.username}")
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
    POST /api/v1/ocr/job/{job_id}/dispatch/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        logger.info(f"Manual dispatch triggered for job_id={job_id} by user={request.user.username}")
        job = get_object_or_404(OCRJob, job_id=job_id)
        
        # Reset job status and trigger dispatch
        job.status = "queued"
        job.retries = 0
        job.error_message = None
        job.save(update_fields=["status", "retries", "error_message", "updated_at"])
        
        # Trigger the dispatch task
        dispatch_ocr_job.delay(job.id)
        logger.info(f"Manual dispatch queued for job {job_id}")
        
        # Audit log
        create_audit_log(
            actor=request.user,
            action="ocr_manual_dispatch",
            entity=job,
            metadata={
                'job_id': str(job.job_id),
                'file': job.file.original_filename,
                'triggered_by': request.user.username
            },
            request=request
        )
        
        return Response({
            "detail": "Dispatch triggered",
            "job_id": str(job.job_id),
        }, status=status.HTTP_202_ACCEPTED)