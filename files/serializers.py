from rest_framework import serializers
from django.conf import settings
from .models import File


class UploadStatusSerializer(serializers.ModelSerializer):
    upload_id = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = ['upload_id', 'original_filename',
                  'file_url', 'status', 'message', 'created_at']

    def get_upload_id(self, obj):
        return str(obj.id)

    def get_file_url(self, obj):
        if hasattr(settings, 'AWS_S3_ENDPOINT_URL') and settings.AWS_S3_ENDPOINT_URL:
            endpoint = settings.AWS_S3_ENDPOINT_URL.rstrip('/')
            return f"{endpoint}/{settings.AWS_STORAGE_BUCKET_NAME}/{obj.s3_key}"
        return None

    def get_message(self, obj):
        messages = {
            'uploaded': 'File uploaded successfully',
            'processing': 'OCR processing in progress',
            'completed': 'Processing completed successfully',
            'failed': 'Processing failed'
        }
        return messages.get(obj.status, 'Unknown status')
