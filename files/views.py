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


class FileUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):

        if not user_has_permission(request.user, 'upload_offer_files'):
            return Response(
                {"detail": "You do not have permission to upload files"},
                status=status.HTTP_403_FORBIDDEN
            )

        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response(
                {"detail": "No file provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        ext = os.path.splitext(file_obj.name)[1].lower()
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']

        if ext not in allowed_extensions:
            return Response(
                {"detail": "Unsupported file type. Only PDF and images are allowed."},
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            )

        unique_id = uuid.uuid4()
        storage_key = f"uploads/{request.user.id}/{unique_id}{ext}"

        try:
            storage = get_storage_adapter()
            storage.upload_fileobj(file_obj, storage_key)

            file_record = File.objects.create(
                s3_key=storage_key,
                original_filename=file_obj.name,
                ware_house_name=request.data.get("ware_house_name"),
                status="uploaded"
            )

            serializer = UploadStatusSerializer(file_record)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"detail": f"Unexpected error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


class UploadStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):

        if not user_has_permission(request.user, 'upload_offer_files'):
            return Response(
                {"detail": "You do not have permission to view upload status"},
                status=status.HTTP_403_FORBIDDEN
            )

        file_obj = get_object_or_404(File, id=id)

        serializer = UploadStatusSerializer(file_obj)

        return Response(serializer.data, status=status.HTTP_200_OK)
