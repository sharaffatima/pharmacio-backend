from celery import shared_task
from ai_integration.models import OCRJob

@shared_task(bind=True, max_retries=3)
def dispatch_ocr_job(self, ocr_job_id: int):
    """
    Background task to dispatch OCR job to OCR engine.
    For now: just demonstrates status transitions.
    """
    job = OCRJob.objects.select_related("file").get(id=ocr_job_id)

    # Emark processing
    job.status = "processing"
    job.error_message = None
    job.save(update_fields=["status", "error_message", "updated_at"])

    try:
        # TODO: call OCR engine here (later step)
        # If success:
        return

    except Exception as e:
        job.retries += 1
        job.status = "failed"
        job.error_message = str(e)
        job.save(update_fields=["retries", "status", "error_message", "updated_at"])
        raise self.retry(exc=e, countdown=10)