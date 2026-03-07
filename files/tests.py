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
        FILE_STORAGE_BACKEND='s3',
        AWS_ACCESS_KEY_ID='test-key',
        AWS_SECRET_ACCESS_KEY='test-secret',
        AWS_S3_ENDPOINT_URL='http://localhost:4566',
        AWS_S3_REGION_NAME='us-east-1',
        AWS_STORAGE_BUCKET_NAME='test-bucket'
    )
    def test_file_upload_success_pdf(self):
        """Test successful PDF file upload"""
        file = SimpleUploadedFile(
            "test_document.pdf",
            b"PDF content here",
            content_type="application/pdf"
        )
        
        with patch('files.storage.boto3.client') as mock_s3:
            mock_s3_client = MagicMock()
            mock_s3.return_value = mock_s3_client
            # Mock the upload_fileobj to return None (success)
            mock_s3_client.upload_fileobj.return_value = None
            
            response = self.client.post(
                '/api/v1/offers/upload/',
                {'file': file, 'ware_house_name': 'Warehouse A'},
                format='multipart'
            )
        
        # Debug: print response if it fails
        if response.status_code != status.HTTP_200_OK:
            print(f"Response: {response.json()}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('upload_id', response.json())
        self.assertEqual(response.json()['original_filename'], 'test_document.pdf')
        self.assertEqual(response.json()['status'], 'uploaded')
        self.assertIn('file_url', response.json())
        
        # Verify File record was created
        self.assertTrue(File.objects.filter(original_filename='test_document.pdf').exists())
        
        # Verify S3 upload was called
        mock_s3_client.upload_fileobj.assert_called_once()

    @override_settings(
        FILE_STORAGE_BACKEND='s3',
        AWS_ACCESS_KEY_ID='test-key',
        AWS_SECRET_ACCESS_KEY='test-secret',
        AWS_S3_ENDPOINT_URL='http://localhost:4566',
        AWS_S3_REGION_NAME='us-east-1',
        AWS_STORAGE_BUCKET_NAME='test-bucket'
    )
    def test_file_upload_success_image(self):
        """Test successful image file upload (JPG)"""
        file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake image content",
            content_type="image/jpeg"
        )
        
        with patch('files.storage.boto3.client') as mock_s3:
            mock_s3_client = MagicMock()
            mock_s3.return_value = mock_s3_client
            
            response = self.client.post(
                '/api/v1/offers/upload/',
                {'file': file, 'ware_house_name': 'Warehouse B'},
                format='multipart'
            )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['original_filename'], 'test_image.jpg')

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
        
        with patch('files.storage.boto3.client') as mock_s3:
            mock_s3_client = MagicMock()
            mock_s3_client.upload_fileobj.side_effect = Exception("S3 connection failed")
            mock_s3.return_value = mock_s3_client
            
            response = self.client.post(
                '/api/v1/offers/upload/',
                {'file': file, 'ware_house_name': 'Warehouse A'},
                format='multipart'
            )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Unexpected error', response.json()['detail'])


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
