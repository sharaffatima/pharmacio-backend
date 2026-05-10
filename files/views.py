import logging
import os
import uuid

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import File
from .serializers import UploadStatusSerializer
from .storage import get_storage_adapter
from ai_integration.models import OCRJob
from ai_integration.tasks import dispatch_ocr_job
from inventory.services.opening_balance_import import (
    apply_opening_balance_rows,
    parse_opening_balance,
)
from rbac.constants import UPLOAD_OFFER_FILES, VIEW_OFFER_FILES
from rbac.permissions import user_has_permission
from rbac.services.audit import create_audit_log

logger = logging.getLogger(__name__)


class FileUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info(f"File upload request from user={request.user.username}")

        if not user_has_permission(request.user, UPLOAD_OFFER_FILES):
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

        max_upload_size = 10 * 1024 * 1024  # 10 MB
        if file_obj.size > max_upload_size:
            logger.warning(f"File too large ({file_obj.size} bytes) from {request.user.username}")
            return Response(
                {"detail": "File size exceeds the 10 MB limit."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )

        ext = os.path.splitext(file_obj.name)[1].lower()
        ocr_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
        opening_balance_extensions = ['.csv', '.xlsx']
        allowed_extensions = ocr_extensions + opening_balance_extensions

        if ext not in allowed_extensions:
            logger.warning(f"Unsupported file type {ext} uploaded by {request.user.username}")
            return Response(
                {"detail": "Unsupported file type. Only PDF, images, CSV, and XLSX files are allowed."},
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            )

        unique_id = uuid.uuid4()
        storage_key = f"uploads/{request.user.id}/{unique_id}{ext}"
        
        logger.debug(f"Uploading file to storage: {storage_key}")

        try:
            opening_balance_rows = None
            if ext in opening_balance_extensions:
                opening_balance_rows = parse_opening_balance(file_obj, ext)

            storage = get_storage_adapter()
            storage.upload_fileobj(file_obj, storage_key)
            logger.info(f"File uploaded successfully: {file_obj.name} -> {storage_key}")

            if ext in opening_balance_extensions:
                with transaction.atomic():
                    file_record = File.objects.create(
                        s3_key=storage_key,
                        original_filename=file_obj.name,
                        ware_house_name=request.data.get("ware_house_name"),
                        status="completed"
                    )

                    import_result = apply_opening_balance_rows(opening_balance_rows)

                    create_audit_log(
                        actor=request.user,
                        action="file_uploaded",
                        entity=file_record,
                        metadata={
                            'filename': file_obj.name,
                            'storage_key': storage_key,
                            'file_id': str(file_record.id),
                            'warehouse_name': request.data.get("ware_house_name"),
                            'import_type': 'opening_balance',
                        },
                        request=request
                    )

                    create_audit_log(
                        actor=request.user,
                        action="opening_balance_imported",
                        entity=file_record,
                        metadata={
                            'filename': file_obj.name,
                            'storage_key': storage_key,
                            'file_id': str(file_record.id),
                            **import_result,
                        },
                        request=request
                    )

                serializer = UploadStatusSerializer(file_record)
                response_data = serializer.data
                response_data["import_result"] = import_result
                logger.info(
                    "Opening balance import completed: file_id=%s, rows=%s, created=%s, updated=%s",
                    file_record.id,
                    import_result["total_rows"],
                    import_result["created_count"],
                    import_result["updated_count"],
                )
                return Response(response_data, status=status.HTTP_201_CREATED)

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

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            logger.warning(f"Opening balance import validation failed for {request.user.username}: {e.detail}")
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception(f"File upload failed for user {request.user.username}: {e}")
            return Response(
                {"detail": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UploadStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        logger.debug(f"Upload status check for file_id={id} by user={request.user.username}")

        if not user_has_permission(request.user, VIEW_OFFER_FILES):
            logger.warning(f"User {request.user.username} attempted status check without permission")
            return Response(
                {"detail": "You do not have permission to view upload status"},
                status=status.HTTP_403_FORBIDDEN
            )

        file_obj = get_object_or_404(File, id=id)

        serializer = UploadStatusSerializer(file_obj)

        return Response(serializer.data, status=status.HTTP_200_OK)
