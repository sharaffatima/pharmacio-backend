from celery import shared_task
from ai_integration.models import OCRJob
from ai_integration.services.ocr_dispatch import dispatch_to_ocr_engine, OCRDispatchError

# Background task to dispatch OCR job to OCR engine.

@shared_task(bind=True, max_retries=3)
def dispatch_ocr_job(self, ocr_job_id: int):
    """
    Background task to dispatch OCR job to OCR engine.
    For now: just demonstrates status transitions.
    """
    job = OCRJob.objects.select_related("file").get(id=ocr_job_id)

    # mark processing
    job.status = "processing"
    job.error_message = None
    job.save(update_fields=["status", "error_message", "updated_at"])

    # Attempt dispatch to OCR engine and handle errors with retry logic
    try:
        dispatch_to_ocr_engine(job=job)
        # Engine accepted the job → DISPATCHED
        job.status = "dispatched"
        job.save(update_fields=["status", "updated_at"])
        return

    except OCRDispatchError as e:
        job.retries += 1
        job.status = "failed"
        job.error_message = str(e)
        job.save(update_fields=["retries", "status", "error_message", "updated_at"])
        raise self.retry(exc=e, countdown=10)