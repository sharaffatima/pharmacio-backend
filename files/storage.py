import os
from abc import ABC, abstractmethod

import boto3
from botocore.config import Config
from django.conf import settings
from django.core.files.storage import FileSystemStorage


class StorageAdapter(ABC):
    @abstractmethod
    def upload_fileobj(self, file_obj, key: str) -> None:
        """Upload an incoming file object to storage under the given key."""

    @abstractmethod
    def get_public_url(self, key: str) -> str | None:
        """Return a public URL for the stored object key, if available."""


class LocalFileSystemStorageAdapter(StorageAdapter):
    def __init__(self) -> None:
        location = getattr(settings, "MEDIA_ROOT", "media")
        base_url = getattr(settings, "MEDIA_URL", "/media/")
        self.storage = FileSystemStorage(location=location, base_url=base_url)

    def upload_fileobj(self, file_obj, key: str) -> None:
        directory = os.path.dirname(key)
        if directory:
            os.makedirs(os.path.join(self.storage.location, directory), exist_ok=True)

        if hasattr(file_obj, "seek"):
            file_obj.seek(0)

        self.storage.save(key, file_obj)

    def get_public_url(self, key: str) -> str | None:
        return self.storage.url(key)


class S3StorageAdapter(StorageAdapter):
    def __init__(self) -> None:
        self.client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            region_name=settings.AWS_S3_REGION_NAME,
            config=Config(signature_version="s3v4"),
            use_ssl=False,
            verify=False,
        )
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    def upload_fileobj(self, file_obj, key: str) -> None:
        self.client.upload_fileobj(file_obj, self.bucket_name, key)

    def get_public_url(self, key: str) -> str | None:
        endpoint = getattr(settings, "AWS_S3_ENDPOINT_URL", "")
        if endpoint:
            return f"{endpoint.rstrip('/')}/{self.bucket_name}/{key}"
        return None


def get_storage_adapter() -> StorageAdapter:
    backend = getattr(settings, "FILE_STORAGE_BACKEND", "")
    backend = backend.lower()

    # Backward compatibility: if FILE_STORAGE_BACKEND is absent, preserve USE_S3 behavior.
    if not backend:
        backend = "s3" if getattr(settings, "USE_S3", False) else "local"

    if backend == "s3":
        return S3StorageAdapter()
    return LocalFileSystemStorageAdapter()