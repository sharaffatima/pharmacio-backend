from django.test import TestCase
import uuid
from decimal import Decimal
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from files.models import File
from ai_integration.models import OCRJob, OCRResults, OCRResultItem
from ai_integration.tasks import dispatch_ocr_job


def _valid_payload():
    return {
        "schema_version": "1.0",
        "created_at": "2026-03-01T12:00:00Z",
        "items": [
            {
                "drug_name": "Paracetamol",
                "company": "ExamplePharma",
                "strength": "500mg",
                "price": 2.99,
                "availability": "in_stock",
                "confidence": 0.93,
                "review_required": False,
            },
            {
                "drug_name": "Ibuprofen",
                "company": "ExamplePharma",
                "strength": "400mg",
                "price": 3.49,
                "availability": "in_stock",
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
    def test_dispatch_task_marks_processing(self):
        f = File.objects.create(
            s3_key="offers/demo3.pdf",
            original_filename="demo3.pdf",
            status="uploaded",
        )
        job = OCRJob.objects.create(file=f, status="queued")

        dispatch_ocr_job.delay(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, "processing")
        self.assertIsNone(job.error_message)


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
        url = reverse("ai-ocr-result")
        body = {"job_id": str(uuid.uuid4()), "payload": _valid_payload()}
        resp = self.client.post(url, data=body, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_callback_invalid_payload_returns_422(self):
        from django.urls import reverse
        url = reverse("ai-ocr-result")
        body = {"job_id": str(self.job.job_id), "payload": {"items": []}}  # missing required keys
        resp = self.client.post(url, data=body, format="json")
        self.assertEqual(resp.status_code, 422)

    def test_callback_creates_result_items_and_completes_job(self):
        from django.urls import reverse
        url = reverse("ai-ocr-result")
        body = {"job_id": str(self.job.job_id), "payload": _valid_payload()}

        resp = self.client.post(url, data=body, format="json")
        self.assertEqual(resp.status_code, 200)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "completed")
        self.assertIsNone(self.job.error_message)

        # OCRResults created
        result = OCRResults.objects.filter(file=self.file).order_by("-created_at").first()
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.ware_house_name, "Warehouse A")

        # Items created
        items = OCRResultItem.objects.filter(ocr_result=result)
        self.assertEqual(items.count(), 2)

        first = items.order_by("id").first()
        self.assertEqual(first.extracted_product_name, "Paracetamol")
        self.assertEqual(first.extracted_strength, "500mg")
        self.assertEqual(first.extracted_company, "ExamplePharma")
        self.assertEqual(first.extracted_quantity, 1)
        self.assertEqual(first.extracted_unit_price, Decimal("2.99"))