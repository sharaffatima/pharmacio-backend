import logging
from django.shortcuts import get_object_or_404
import os
import uuid
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from .models import File
from .serializers import UploadStatusSerializer
from rbac.permissions import user_has_permission
from .storage import get_storage_adapter
from ai_integration.models import OCRJob
from ai_integration.tasks import dispatch_ocr_job
from rbac.services.audit import create_audit_log

logger = logging.getLogger(__name__)


class FileUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info(f"File upload request from user={request.user.username}")

        if not user_has_permission(request.user, 'upload_offer_files'):
            logger.warning(f"User {request.user.username} attempted file upload without permission")
            return Response(
                {"detail": "You do not have permission to upload files"},
                status=status.HTTP_403_FORBIDDEN
            )

        file_obj = request.FILES.get("file")
        if not file_obj:
            logger.warning(f"File upload request from {request.user.username} with no file provided")
            return Response(
                {"detail": "No file provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        ext = os.path.splitext(file_obj.name)[1].lower()
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']

        if ext not in allowed_extensions:
            logger.warning(f"Unsupported file type {ext} uploaded by {request.user.username}")
            return Response(
                {"detail": "Unsupported file type. Only PDF and images are allowed."},
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            )

        unique_id = uuid.uuid4()
        storage_key = f"uploads/{request.user.id}/{unique_id}{ext}"
        
        logger.debug(f"Uploading file to storage: {storage_key}")

        try:
            storage = get_storage_adapter()
            storage.upload_fileobj(file_obj, storage_key)
            logger.info(f"File uploaded successfully: {file_obj.name} -> {storage_key}")

            file_record = File.objects.create(
                s3_key=storage_key,
                original_filename=file_obj.name,
                ware_house_name=request.data.get("ware_house_name"),
                status="uploaded"
            )

            # Create OCRJob for this file
            ocr_job = OCRJob.objects.create(
                file=file_record,
                status="queued"
            )

            # Trigger async dispatch of OCR job to AI engine
            dispatch_ocr_job.delay(ocr_job.id)
            logger.info(f"OCR job created and dispatched: job_id={ocr_job.job_id}, file_id={file_record.id}")
            
            # Audit log
            create_audit_log(
                actor=request.user,
                action="file_uploaded",
                entity=file_record,
                metadata={
                    'filename': file_obj.name,
                    'storage_key': storage_key,
                    'file_id': str(file_record.id),
                    'warehouse_name': request.data.get("ware_house_name"),
                    'ocr_job_id': str(ocr_job.job_id)
                },
                request=request
            )

            serializer = UploadStatusSerializer(file_record)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"File upload failed for user {request.user.username}: {e}")
            return Response(
                {"detail": f"Unexpected error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


class UploadStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        logger.debug(f"Upload status check for file_id={id} by user={request.user.username}")

        if not user_has_permission(request.user, 'upload_offer_files'):
            logger.warning(f"User {request.user.username} attempted status check without permission")
            return Response(
                {"detail": "You do not have permission to view upload status"},
                status=status.HTTP_403_FORBIDDEN
            )

        file_obj = get_object_or_404(File, id=id)

        serializer = UploadStatusSerializer(file_obj)

        return Response(serializer.data, status=status.HTTP_200_OK)
