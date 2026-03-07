import logging
from celery import shared_task
from ai_integration.models import OCRJob
from ai_integration.services.ocr_dispatch import dispatch_to_ocr_engine, OCRDispatchError

logger = logging.getLogger(__name__)

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
        logger.warning(f"OCRJob with id={ocr_job_id} not found, task abandoned")
        return
    
    logger.info(f"Starting OCR dispatch for job_id={job.job_id}, file={job.file.original_filename}")

    # Mark processing
    job.status = "processing"
    job.error_message = None
    job.save(update_fields=["status", "error_message", "updated_at"])
    
    # Sync File status
    job.file.status = "processing"
    job.file.save(update_fields=["status"])
    logger.debug(f"Job {job.job_id} status updated to processing")

    # Attempt dispatch to OCR engine and handle errors with retry logic
    try:
        dispatch_to_ocr_engine(job=job)
        # Engine accepted the job → DISPATCHED
        job.status = "dispatched"
        job.error_message = None
        job.save(update_fields=["status", "error_message", "updated_at"])
        logger.info(f"Successfully dispatched job {job.job_id} to OCR engine")
        return

    except OCRDispatchError as e:
        job.retries += 1
        job.error_message = str(e)
        logger.warning(f"Dispatch failed for job {job.job_id}, retry {self.request.retries + 1}/{self.max_retries}: {e}")

        # If max retries exceeded, mark as failed
        if self.request.retries >= self.max_retries:
            job.status = "failed"
            job.save(update_fields=["retries", "status", "error_message", "updated_at"])
            
            # Sync File status
            job.file.status = "failed"
            job.file.save(update_fields=["status"])
            logger.error(f"Job {job.job_id} failed after {self.max_retries} retries: {e}")
            return

        # Otherwise, save current state and retry with exponential backoff
        job.status = "processing"
        job.save(update_fields=["retries", "status", "error_message", "updated_at"])

        # Retry with exponential backoff: 10s, 20s, 40s
        countdown = 10 * (2 ** self.request.retries)
        logger.info(f"Retrying job {job.job_id} in {countdown}s")
        raise self.retry(exc=e, countdown=countdown)