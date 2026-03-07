from celery import shared_task
from ai_integration.models import OCRJob
from ai_integration.services.ocr_dispatch import dispatch_to_ocr_engine, OCRDispatchError

# Background task to dispatch OCR job to OCR engine.

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def dispatch_ocr_job(self, ocr_job_id: int):
    """
    Background task to dispatch OCR job to OCR engine.
    - Updates job status to PROCESSING when starting
    - Attempts to dispatch to OCR engine with retry logic
    - Updates job status to DISPATCHED on success
    - Updates job status to FAILED on final failure
    """
    try:
        job = OCRJob.objects.select_related("file").get(id=ocr_job_id)
    except OCRJob.DoesNotExist:
        # Job was deleted, abandon task
        return

    # Mark processing
    job.status = "processing"
    job.error_message = None
    job.save(update_fields=["status", "error_message", "updated_at"])

    # Attempt dispatch to OCR engine and handle errors with retry logic
    try:
        dispatch_to_ocr_engine(job=job)
        # Engine accepted the job → DISPATCHED
        job.status = "dispatched"
        job.error_message = None
        job.save(update_fields=["status", "error_message", "updated_at"])
        return

    except OCRDispatchError as e:
        job.retries += 1
        job.error_message = str(e)

        # If max retries exceeded, mark as failed
        if self.request.retries >= self.max_retries:
            job.status = "failed"
            job.save(update_fields=["retries", "status", "error_message", "updated_at"])
            return

        # Otherwise, save current state and retry with exponential backoff
        job.status = "processing"
        job.save(update_fields=["retries", "status", "error_message", "updated_at"])

        # Retry with exponential backoff: 10s, 20s, 40s
        countdown = 10 * (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=countdown)