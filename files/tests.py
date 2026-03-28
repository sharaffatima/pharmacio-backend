from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from .models import File
from rbac.models import Permission, Role, UserRole

User = get_user_model()


class FileUploadViewTests(TestCase):
    """Test cases for FileUploadView"""

    def setUp(self):
        """Set up test client and test user"""
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        
        # Create permission
        self.permission = Permission.objects.create(
            code='upload_offer_files',
            action='create'
        )
        
        # Create role with permission
        self.role = Role.objects.create(name='admin')
        self.role.permissions.add(self.permission)
        
        # Assign role to user
        UserRole.objects.create(user=self.user, role=self.role)
        
        # Authenticate client
        self.client.force_authenticate(user=self.user)

    @override_settings(
        FILE_STORAGE_BACKEND='local',
        MEDIA_ROOT='/tmp',
    )
    @patch('files.views.dispatch_ocr_job.delay')
    @patch('files.views.get_storage_adapter')
    def test_file_upload_success_pdf(self, mock_storage_adapter, mock_dispatch_task):
        """Test successful PDF file upload"""
        mock_storage_instance = MagicMock()
        mock_storage_adapter.return_value = mock_storage_instance

        file = SimpleUploadedFile(
            "test_document.pdf",
            b"PDF content here",
            content_type="application/pdf"
        )

        response = self.client.post(
            '/api/v1/offers/upload/',
            {'file': file, 'ware_house_name': 'Warehouse A'},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('upload_id', response.json())
        self.assertEqual(response.json()['original_filename'], 'test_document.pdf')
        self.assertEqual(response.json()['status'], 'uploaded')
        self.assertIn('file_url', response.json())
        
        # Verify File record was created
        self.assertTrue(File.objects.filter(original_filename='test_document.pdf').exists())

        # Verify storage upload was called
        mock_storage_instance.upload_fileobj.assert_called_once()
        mock_dispatch_task.assert_called_once()

    @override_settings(
        FILE_STORAGE_BACKEND='local',
        MEDIA_ROOT='/tmp',
    )
    @patch('files.views.dispatch_ocr_job.delay')
    @patch('files.views.get_storage_adapter')
    def test_file_upload_success_image(self, mock_storage_adapter, mock_dispatch_task):
        """Test successful image file upload (JPG)"""
        mock_storage_instance = MagicMock()
        mock_storage_adapter.return_value = mock_storage_instance

        file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake image content",
            content_type="image/jpeg"
        )

        response = self.client.post(
            '/api/v1/offers/upload/',
            {'file': file, 'ware_house_name': 'Warehouse B'},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['original_filename'], 'test_image.jpg')
        mock_storage_instance.upload_fileobj.assert_called_once()
        mock_dispatch_task.assert_called_once()

    def test_file_upload_unsupported_extension(self):
        """Test upload with unsupported file type"""
        file = SimpleUploadedFile(
            "test_file.exe",
            b"executable content",
            content_type="application/x-msdownload"
        )
        
        response = self.client.post(
            '/api/v1/offers/upload/',
            {'file': file, 'ware_house_name': 'Warehouse A'},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        self.assertIn('Unsupported file type', response.json()['detail'])

    def test_file_upload_no_file_provided(self):
        """Test upload without providing a file"""
        response = self.client.post(
            '/api/v1/offers/upload/',
            {'ware_house_name': 'Warehouse A'},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('No file provided', response.json()['detail'])

    def test_file_upload_without_permission(self):
        """Test upload without required permission"""
        # Create a new user without permission
        user_no_perm = User.objects.create_user(
            username='nopermuser',
            email='noperm@test.com',
            password='testpass123'
        )
        
        client = APIClient()
        client.force_authenticate(user=user_no_perm)
        
        file = SimpleUploadedFile(
            "test.pdf",
            b"PDF content",
            content_type="application/pdf"
        )
        
        response = client.post(
            '/api/v1/offers/upload/',
            {'file': file, 'ware_house_name': 'Warehouse A'},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('permission', response.json()['detail'].lower())

    def test_file_upload_unauthenticated(self):
        """Test upload without authentication"""
        client = APIClient()
        
        file = SimpleUploadedFile(
            "test.pdf",
            b"PDF content",
            content_type="application/pdf"
        )
        
        response = client.post(
            '/api/v1/offers/upload/',
            {'file': file, 'ware_house_name': 'Warehouse A'},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(
        FILE_STORAGE_BACKEND='local',
        MEDIA_ROOT='/tmp',
    )
    @patch('files.views.dispatch_ocr_job.delay')
    @patch('files.views.get_storage_adapter')
    def test_file_upload_allows_legacy_admin_role_field(
        self, mock_storage_adapter, mock_dispatch_task
    ):
        """A user with role='admin' should be allowed even without UserRole mapping."""
        legacy_admin = User.objects.create_user(
            username='legacyadmin',
            email='legacyadmin@test.com',
            password='testpass123',
            role='admin'
        )

        client = APIClient()
        client.force_authenticate(user=legacy_admin)

        mock_storage_instance = MagicMock()
        mock_storage_adapter.return_value = mock_storage_instance

        file = SimpleUploadedFile(
            "legacy_admin_upload.pdf",
            b"PDF content",
            content_type="application/pdf"
        )

        response = client.post(
            '/api/v1/offers/upload/',
            {'file': file, 'ware_house_name': 'Warehouse A'},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_storage_instance.upload_fileobj.assert_called_once()
        mock_dispatch_task.assert_called_once()

    @override_settings(
        FILE_STORAGE_BACKEND='s3',
        AWS_ACCESS_KEY_ID='test-key',
        AWS_SECRET_ACCESS_KEY='test-secret',
        AWS_S3_ENDPOINT_URL='http://localhost:4566',
        AWS_S3_REGION_NAME='us-east-1',
        AWS_STORAGE_BUCKET_NAME='test-bucket'
    )
    def test_file_upload_s3_error(self):
        """Test handling of S3 upload error"""
        file = SimpleUploadedFile(
            "test.pdf",
            b"PDF content",
            content_type="application/pdf"
        )
        
        mock_adapter = MagicMock()
        mock_adapter.upload_fileobj.side_effect = Exception("S3 connection failed")
        
        with patch('files.views.get_storage_adapter', return_value=mock_adapter):
            response = self.client.post(
                '/api/v1/offers/upload/',
                {'file': file, 'ware_house_name': 'Warehouse A'},
                format='multipart'
            )
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('unexpected error', response.json()['detail'].lower())


class UploadStatusViewTests(TestCase):
    """Test cases for UploadStatusView"""

    def setUp(self):
        """Set up test client, user, and file record"""
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        
        # Create permission
        self.permission = Permission.objects.create(
            code='upload_offer_files',
            action='create'
        )
        
        # Create role with permission
        self.role = Role.objects.create(name='admin')
        self.role.permissions.add(self.permission)
        
        # Assign role to user
        UserRole.objects.create(user=self.user, role=self.role)
        
        # Authenticate client
        self.client.force_authenticate(user=self.user)
        
        # Create test file record
        self.file = File.objects.create(
            s3_key='uploads/1/test-uuid.pdf',
            original_filename='test.pdf',
            ware_house_name='Warehouse A',
            status='uploaded'
        )

    def test_get_upload_status_success(self):
        """Test retrieving upload status"""
        response = self.client.get(
            f'/api/v1/offers/uploads/{self.file.id}/status/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['upload_id'], str(self.file.id))
        self.assertEqual(data['original_filename'], 'test.pdf')
        self.assertEqual(data['status'], 'uploaded')
        self.assertEqual(data['message'], 'File uploaded successfully')

    def test_get_upload_status_without_permission(self):
        """Test status check without required permission"""
        user_no_perm = User.objects.create_user(
            username='nopermuser',
            email='noperm@test.com',
            password='testpass123'
        )
        
        client = APIClient()
        client.force_authenticate(user=user_no_perm)
        
        response = client.get(
            f'/api/v1/offers/uploads/{self.file.id}/status/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_upload_status_unauthenticated(self):
        """Test status check without authentication"""
        client = APIClient()
        
        response = client.get(
            f'/api/v1/offers/uploads/{self.file.id}/status/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_upload_status_nonexistent_id(self):
        """Test status check with invalid upload ID"""
        response = self.client.get(
            '/api/v1/offers/uploads/00000000-0000-0000-0000-000000000000/status/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_upload_status_messages(self):
        """Test status messages for different states"""
        test_cases = [
            ('uploaded', 'File uploaded successfully'),
            ('processing', 'OCR processing in progress'),
            ('completed', 'Processing completed successfully'),
            ('failed', 'Processing failed'),
        ]
        
        for status_value, expected_message in test_cases:
            file = File.objects.create(
                s3_key=f'uploads/1/{status_value}.pdf',
                original_filename=f'{status_value}.pdf',
                ware_house_name='Warehouse A',
                status=status_value
            )
            
            response = self.client.get(
                f'/api/v1/offers/uploads/{file.id}/status/'
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.json()['message'], expected_message)


class FileUploadCreatesOCRJobTests(TestCase):
    """Test cases for automatic OCRJob creation on file upload"""

    def setUp(self):
        """Set up test client and test user"""
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        
        # Create permission
        self.permission = Permission.objects.create(
            code='upload_offer_files',
            action='create'
        )
        
        # Create role with permission
        self.role = Role.objects.create(name='admin')
        self.role.permissions.add(self.permission)
        
        # Assign role to user
        UserRole.objects.create(user=self.user, role=self.role)
        
        # Authenticate client
        self.client.force_authenticate(user=self.user)

    @override_settings(
        FILE_STORAGE_BACKEND='local',
        MEDIA_ROOT='/tmp',
    )
    @patch('files.views.dispatch_ocr_job.delay')
    @patch('files.views.get_storage_adapter')
    def test_file_upload_creates_ocr_job_and_triggers_dispatch(
        self, mock_storage, mock_dispatch_task
    ):
        """Test that file upload creates OCRJob and triggers dispatch task"""
        from ai_integration.models import OCRJob
        
        # Mock storage
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        
        file = SimpleUploadedFile(
            "test_document.pdf",
            b"PDF content here",
            content_type="application/pdf"
        )
        
        response = self.client.post(
            '/api/v1/offers/upload/',
            {'file': file, 'ware_house_name': 'Warehouse A'},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify File record was created
        uploaded_file = File.objects.filter(
            original_filename='test_document.pdf'
        ).first()
        self.assertIsNotNone(uploaded_file)
        
        # Verify OCRJob was created
        ocr_job = OCRJob.objects.filter(file=uploaded_file).first()
        self.assertIsNotNone(ocr_job)
        self.assertEqual(ocr_job.status, "queued")
        self.assertEqual(ocr_job.retries, 0)
        self.assertIsNone(ocr_job.error_message)
        
        # Verify dispatch task was triggered
        mock_dispatch_task.assert_called_once_with(ocr_job.id)

    @override_settings(
        FILE_STORAGE_BACKEND='local',
        MEDIA_ROOT='/tmp',
    )
    @patch('files.views.dispatch_ocr_job.delay')
    @patch('files.views.get_storage_adapter')
    def test_ocr_job_linked_to_correct_file(
        self, mock_storage, mock_dispatch_task
    ):
        """Test that OCRJob is correctly linked to the uploaded file"""
        from ai_integration.models import OCRJob
        
        # Mock storage
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        
        file = SimpleUploadedFile(
            "warehouse_inventory.pdf",
            b"PDF content",
            content_type="application/pdf"
        )
        
        warehouse_name = "Central Warehouse"
        response = self.client.post(
            '/api/v1/offers/upload/',
            {'file': file, 'ware_house_name': warehouse_name},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Get the created file
        uploaded_file = File.objects.get(
            original_filename='warehouse_inventory.pdf'
        )
        
        # Get the OCRJob
        ocr_job = OCRJob.objects.get(file=uploaded_file)
        
        # Verify the relationship
        self.assertEqual(ocr_job.file.id, uploaded_file.id)
        self.assertEqual(ocr_job.file.ware_house_name, warehouse_name)
        self.assertEqual(ocr_job.file.original_filename, 'warehouse_inventory.pdf')
