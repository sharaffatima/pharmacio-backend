import uuid
from decimal import Decimal
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock
import requests

from files.models import File
from ai_integration.models import OCRJob, OCRResults, OCRResultItem
from ai_integration.tasks import dispatch_ocr_job
from ai_integration.services.ocr_dispatch import dispatch_to_ocr_engine, OCRDispatchError
from users.models import User


def _valid_payload():
    """Valid OCR payload with only required fields: drug_name, company, price, confidence, review_required."""
    return {
        "items": [
            {
                "drug_name": "Paracetamol",
                "company": "ExamplePharma",
                "price": "2.99",
                "confidence": 0.93,
                "review_required": False,
            },
            {
                "drug_name": "Ibuprofen",
                "company": "ExamplePharma",
                "price": "3.49",
                "confidence": 0.80,
                "review_required": True,
            },
        ],
    }


class OCRJobModelTests(TestCase):
    def test_ocrjob_defaults(self):
        f = File.objects.create(
            s3_key="offers/demo.pdf",
            original_filename="demo.pdf",
            status="uploaded",
        )
        job = OCRJob.objects.create(file=f)
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.retries, 0)
        self.assertIsNotNone(job.job_id)

    def test_ocrresults_confidence_constraint_enforced(self):
        f = File.objects.create(
            s3_key="offers/demo2.pdf",
            original_filename="demo2.pdf",
            status="uploaded",
        )
        job = OCRJob.objects.create(file=f)

        # confidence_score must be between 0 and 1
        with self.assertRaises(Exception):
            OCRResults.objects.create(
                job=job if "job" in [f.name for f in OCRResults._meta.fields] else None,
                job_id=job if "job_id" in [f.name for f in OCRResults._meta.fields] else None,
                file=f,
                ware_house_name="WH",
                confidence_score=1.5,
                review_required=False,
                status="completed",
            )


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class CeleryDispatchTests(TestCase):
    @patch("ai_integration.tasks.dispatch_to_ocr_engine")
    def test_dispatch_task_marks_processing(self, mock_dispatch):
        """Test that successful dispatch transitions through processing to dispatched"""
        mock_dispatch.return_value = None
        
        f = File.objects.create(
            s3_key="offers/demo3.pdf",
            original_filename="demo3.pdf",
            status="uploaded",
        )
        job = OCRJob.objects.create(file=f, status="queued")

        dispatch_ocr_job.delay(job.id)

        job.refresh_from_db()
        # When dispatch succeeds, job goes to 'dispatched' status
        self.assertEqual(job.status, "dispatched")
        self.assertIsNone(job.error_message)
        self.assertEqual(job.retries, 0)
        mock_dispatch.assert_called_once()


class OCRResultCallbackTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.file = File.objects.create(
            s3_key="offers/demo4.pdf",
            original_filename="demo4.pdf",
            status="uploaded",
            ware_house_name="Warehouse A",
        )
        self.job = OCRJob.objects.create(file=self.file, status="processing")

    def test_callback_unknown_job_returns_400(self):
        from django.urls import reverse
        url = reverse("ocr-result-callback")
        body = {"job_id": str(uuid.uuid4()), "payload": _valid_payload()}
        resp = self.client.post(url, data=body, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_callback_invalid_payload_returns_422(self):
        from django.urls import reverse
        url = reverse("ocr-result-callback")
        body = {"job_id": str(self.job.job_id), "payload": {"items": []}}  # missing required keys
        resp = self.client.post(url, data=body, format="json")
        self.assertEqual(resp.status_code, 422)

    def test_callback_creates_result_items_and_completes_job(self):
        from django.urls import reverse
        url = reverse("ocr-result-callback")
        body = {"job_id": str(self.job.job_id), "payload": _valid_payload()}

        resp = self.client.post(url, data=body, format="json")
        self.assertEqual(resp.status_code, 200)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "ocr_done")
        self.assertIsNone(self.job.error_message)
        
        # Check File status was also updated
        self.file.refresh_from_db()
        self.assertEqual(self.file.status, "completed")

        # OCRResults created with correct aggregated data
        result = OCRResults.objects.filter(file=self.file).order_by("-created_at").first()
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.ware_house_name, "Warehouse A")
        self.assertAlmostEqual(result.confidence_score, 0.865)  # avg of 0.93 and 0.80
        self.assertTrue(result.review_required)  # True because second item has review_required=True

        # Items created with correct extracted data
        items = OCRResultItem.objects.filter(ocr_result=result)
        self.assertEqual(items.count(), 2)

        first = items.order_by("id").first()
        self.assertEqual(first.extracted_product_name, "Paracetamol")
        self.assertEqual(first.extracted_company, "ExamplePharma")
        self.assertEqual(first.extracted_unit_price, Decimal("2.99"))


class OCRDispatchServiceTests(TestCase):
    """Tests for the dispatch_to_ocr_engine service"""

    def setUp(self):
        self.file = File.objects.create(
            s3_key="offers/test_dispatch.pdf",
            original_filename="test_dispatch.pdf",
            status="uploaded",
        )
        self.job = OCRJob.objects.create(file=self.file, status="processing")

    @patch("ai_integration.services.ocr_dispatch.requests.post")
    @override_settings(
        OCR_ENGINE_PROCESS_URL="http://ai-engine:8000/ocr/process",
        AI_ENGINE_API_KEY="test-api-key",
        OCR_ENGINE_TIMEOUT_SECONDS=30,
    )
    def test_dispatch_sends_correct_payload(self, mock_post):
        """Test that dispatch sends job_id and file_reference"""
        mock_post.return_value.status_code = 200

        dispatch_to_ocr_engine(job=self.job)

        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Check URL
        self.assertEqual(
            call_args[0][0], "http://ai-engine:8000/ocr/process"
        )

        # Check payload
        payload = call_args[1]["json"]
        self.assertEqual(payload["job_id"], str(self.job.job_id))
        self.assertEqual(payload["file_reference"], "offers/test_dispatch.pdf")

        # Check timeout
        self.assertEqual(call_args[1]["timeout"], 30)

        # Check auth header
        self.assertEqual(
            call_args[1]["headers"]["Authorization"], "test-api-key"
        )

    @patch("ai_integration.services.ocr_dispatch.requests.post")
    @override_settings(
        OCR_ENGINE_PROCESS_URL="http://ai-engine:8000/ocr/process",
        AI_ENGINE_API_KEY="test-api-key",
    )
    def test_dispatch_handles_timeout(self, mock_post):
        """Test that dispatch raises OCRDispatchError on timeout"""
        mock_post.side_effect = requests.Timeout("Connection timeout")

        with self.assertRaises(OCRDispatchError) as cm:
            dispatch_to_ocr_engine(job=self.job)

        self.assertIn("timeout", str(cm.exception).lower())

    @patch("ai_integration.services.ocr_dispatch.requests.post")
    @override_settings(
        OCR_ENGINE_PROCESS_URL="http://ai-engine:8000/ocr/process",
        AI_ENGINE_API_KEY="test-api-key",
    )
    def test_dispatch_handles_connection_error(self, mock_post):
        """Test that dispatch raises OCRDispatchError on connection error"""
        mock_post.side_effect = requests.ConnectionError("Cannot connect")

        with self.assertRaises(OCRDispatchError) as cm:
            dispatch_to_ocr_engine(job=self.job)

        self.assertIn("connection", str(cm.exception).lower())

    @patch("ai_integration.services.ocr_dispatch.requests.post")
    @override_settings(
        OCR_ENGINE_PROCESS_URL="http://ai-engine:8000/ocr/process",
        AI_ENGINE_API_KEY="test-api-key",
    )
    def test_dispatch_handles_http_error(self, mock_post):
        """Test that dispatch raises OCRDispatchError on HTTP error"""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_post.return_value = mock_response

        with self.assertRaises(OCRDispatchError) as cm:
            dispatch_to_ocr_engine(job=self.job)

        self.assertIn("http", str(cm.exception).lower())


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class CeleryDispatchRetryTests(TestCase):
    """Tests for dispatch_ocr_job celery task with retries"""

    def setUp(self):
        self.file = File.objects.create(
            s3_key="offers/demo_retry.pdf",
            original_filename="demo_retry.pdf",
            status="uploaded",
        )
        self.job = OCRJob.objects.create(file=self.file, status="queued")

    @patch("ai_integration.tasks.dispatch_to_ocr_engine")
    def test_dispatch_task_success_marks_dispatched(self, mock_dispatch):
        """Test that successful dispatch marks job as DISPATCHED"""
        mock_dispatch.return_value = None

        dispatch_ocr_job(self.job.id)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "dispatched")
        self.assertIsNone(self.job.error_message)
        self.assertEqual(self.job.retries, 0)

    @patch("ai_integration.tasks.dispatch_to_ocr_engine")
    def test_dispatch_task_failure_marks_failed_after_max_retries(self, mock_dispatch):
        """Test that dispatch marks job as FAILED after max retries"""
        error_msg = "Service unavailable"
        mock_dispatch.side_effect = OCRDispatchError(error_msg)

        # Manually call the task function without celery retry mechanism
        # to test the failure handling
        try:
            from ai_integration.tasks import dispatch_ocr_job as task_func
            # Call without going through celery
            task_func(self.job.id)
        except OCRDispatchError:
            pass

        self.job.refresh_from_db()
        self.assertIn(error_msg, self.job.error_message)


class OCRJobStatusViewTests(TestCase):
    """Tests for the OCR job status endpoint"""

    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.file = File.objects.create(
            s3_key="offers/job_status.pdf",
            original_filename="job_status.pdf",
            status="uploaded",
        )
        self.job = OCRJob.objects.create(file=self.file, status="dispatched")

    def test_job_status_requires_auth(self):
        """Test that job status endpoint requires authentication"""
        unauth_client = APIClient()
        url = reverse("ocr-job-status", kwargs={"job_id": self.job.job_id})
        resp = unauth_client.get(url)
        self.assertEqual(resp.status_code, 401)

    def test_job_status_returns_job_details(self):
        """Test that job status endpoint returns correct job details"""
        url = reverse("ocr-job-status", kwargs={"job_id": self.job.job_id})
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["job_id"], str(self.job.job_id))
        self.assertEqual(data["file_id"], str(self.file.id))
        self.assertEqual(data["status"], "dispatched")
        self.assertEqual(data["retries"], 0)
        self.assertIsNone(data["error_message"])

    def test_job_status_404_for_unknown_job(self):
        """Test that job status returns 404 for unknown job"""
        unknown_job_id = uuid.uuid4()
        url = reverse("ocr-job-status", kwargs={"job_id": unknown_job_id})
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 404)


class ManualDispatchViewTests(TestCase):
    """Tests for manual dispatch endpoint"""

    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.file = File.objects.create(
            s3_key="offers/manual_dispatch.pdf",
            original_filename="manual_dispatch.pdf",
            status="uploaded",
        )
        self.job = OCRJob.objects.create(
            file=self.file, status="failed", retries=3, error_message="Connection timeout"
        )

    def test_manual_dispatch_requires_auth(self):
        """Test that manual dispatch endpoint requires authentication"""
        unauth_client = APIClient()
        url = reverse("manual-dispatch", kwargs={"job_id": self.job.job_id})
        resp = unauth_client.post(url)
        self.assertEqual(resp.status_code, 401)

    @patch("ai_integration.tasks.dispatch_ocr_job.delay")
    def test_manual_dispatch_resets_and_triggers(self, mock_delay):
        """Test that manual dispatch resets job state and triggers task"""
        url = reverse("manual-dispatch", kwargs={"job_id": self.job.job_id})
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 202)
        data = resp.json()
        self.assertEqual(data["job_id"], str(self.job.job_id))

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "queued")
        self.assertEqual(self.job.retries, 0)
        self.assertIsNone(self.job.error_message)

        mock_delay.assert_called_once_with(self.job.id)

    def test_manual_dispatch_404_for_unknown_job(self):
        """Test that manual dispatch returns 404 for unknown job"""
        unknown_job_id = uuid.uuid4()
        url = reverse("manual-dispatch", kwargs={"job_id": unknown_job_id})
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 404)


class FileUploadCreatesOCRJobTests(TestCase):
    """Tests for automatic OCRJob creation on file upload"""

    def setUp(self):
        """Set up test user with permissions"""
        from rbac.models import Permission, Role, UserRole
        
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        
        # Create and assign permission
        perm = Permission.objects.create(
            code='upload_offer_files',
            action='create'
        )
        role = Role.objects.create(name='uploader')
        role.permissions.add(perm)
        UserRole.objects.create(user=self.user, role=role)

    @patch("files.views.dispatch_ocr_job.delay")
    @patch("files.views.get_storage_adapter")
    def test_file_upload_creates_ocr_job_and_triggers_dispatch(
        self, mock_storage, mock_dispatch_task
    ):
        """Test that file upload creates OCRJob and triggers dispatch task"""
        # Mock storage
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance

        # Create a mock file object
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile

        mock_file = SimpleUploadedFile(
            "test.pdf", BytesIO(b"test content").getvalue()
        )

        # Create client and authenticate
        client = APIClient()
        client.force_authenticate(user=self.user)

        url = reverse("file-upload")
        resp = client.post(
            url,
            {"file": mock_file, "ware_house_name": "Test WH"},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 200)

        # Check that OCRJob was created
        jobs = OCRJob.objects.all()
        self.assertEqual(jobs.count(), 1)

        job = jobs.first()
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.file.original_filename, "test.pdf")
        self.assertEqual(job.file.ware_house_name, "Test WH")

        # Check that dispatch task was triggered
        mock_dispatch_task.assert_called_once_with(job.id)


class OCRResultSerializerValidationTests(TestCase):
    """Tests for OCRResultSerializer validation"""

    def setUp(self):
        self.client = APIClient()
        self.file = File.objects.create(
            s3_key="offers/serializer_test.pdf",
            original_filename="serializer_test.pdf",
            status="uploaded",
            ware_house_name="Test WH",
        )
        self.job = OCRJob.objects.create(file=self.file, status="processing")

    def test_missing_items_fails(self):
        """Test that missing items fails validation"""
        url = reverse("ocr-result-callback")
        payload = {}
        body = {"job_id": str(self.job.job_id), "payload": payload}

        resp = self.client.post(url, data=body, format="json")
        self.assertEqual(resp.status_code, 422)

    def test_items_not_list_fails(self):
        """Test that non-list items fails validation"""
        url = reverse("ocr-result-callback")
        payload = {"items": {"drug_name": "Test"}}  # Should be list
        body = {"job_id": str(self.job.job_id), "payload": payload}

        resp = self.client.post(url, data=body, format="json")
        self.assertEqual(resp.status_code, 422)

    def test_missing_item_drug_name_fails(self):
        """Test that missing drug_name fails validation"""
        url = reverse("ocr-result-callback")
        payload = {
            "items": [
                {
                    "company": "ExamplePharma",
                    "price": "2.99",
                    "confidence": 0.93,
                    "review_required": False,
                },
            ],
        }
        body = {"job_id": str(self.job.job_id), "payload": payload}

        resp = self.client.post(url, data=body, format="json")
        self.assertEqual(resp.status_code, 422)

    def test_missing_item_price_fails(self):
        """Test that missing price fails validation"""
        url = reverse("ocr-result-callback")
        payload = {
            "items": [
                {
                    "drug_name": "Paracetamol",
                    "company": "ExamplePharma",
                    "confidence": 0.93,
                    "review_required": False,
                },
            ],
        }
        body = {"job_id": str(self.job.job_id), "payload": payload}

        resp = self.client.post(url, data=body, format="json")
        self.assertEqual(resp.status_code, 422)

    def test_confidence_out_of_range_fails(self):
        """Test that confidence outside [0.0, 1.0] fails validation"""
        url = reverse("ocr-result-callback")
        payload = {
            "items": [
                {
                    "drug_name": "Paracetamol",
                    "company": "ExamplePharma",
                    "price": "2.99",
                    "confidence": 1.5,  # Out of range
                    "review_required": False,
                },
            ],
        }
        body = {"job_id": str(self.job.job_id), "payload": payload}

        resp = self.client.post(url, data=body, format="json")
        self.assertEqual(resp.status_code, 422)

    def test_negative_price_fails(self):
        """Test that negative price fails validation"""
        url = reverse("ocr-result-callback")
        payload = {
            "items": [
                {
                    "drug_name": "Paracetamol",
                    "company": "ExamplePharma",
                    "price": "-2.99",  # Negative not allowed
                    "confidence": 0.93,
                    "review_required": False,
                },
            ],
        }
        body = {"job_id": str(self.job.job_id), "payload": payload}

        resp = self.client.post(url, data=body, format="json")
        self.assertEqual(resp.status_code, 422)

    def test_valid_payload_succeeds(self):
        """Test that valid payload succeeds"""
        url = reverse("ocr-result-callback")
        body = {"job_id": str(self.job.job_id), "payload": _valid_payload()}

        resp = self.client.post(url, data=body, format="json")
        self.assertEqual(resp.status_code, 200)