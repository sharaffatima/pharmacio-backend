from rest_framework import serializers
from .models import File
from .storage import get_storage_adapter


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
        storage = get_storage_adapter()
        return storage.get_public_url(obj.s3_key)

    def get_message(self, obj):
        messages = {
            'uploaded': 'File uploaded successfully',
            'processing': 'OCR processing in progress',
            'completed': 'Processing completed successfully',
            'failed': 'Processing failed'
        }
        return messages.get(obj.status, 'Unknown status')
