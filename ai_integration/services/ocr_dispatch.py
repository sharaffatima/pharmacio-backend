import logging
import requests
from django.conf import settings
from django.db.models import F
from ai_integration.models import OCRJob
from inventory.models import Inventory

logger = logging.getLogger(__name__)

# Service module responsible for dispatching OCR jobs to the OCR engine and handling related errors.

class OCRDispatchError(Exception):
    pass


def dispatch_to_ocr_engine(*, job: OCRJob) -> None:
    """
    Sends {job_id, file_reference, target_items} to the OCR engine.
    Raises OCRDispatchError on failure.
    """
    low_stock_items = Inventory.objects.filter(quantity_on_hand__lte=F('min_threshold'))
    target_items = [
        {"product_name": item.product_name, "strength": item.strength}
        for item in low_stock_items
    ]

    payload = {
        "job_id": str(job.job_id),
        "file_reference": job.file.s3_key,
        "target_items": target_items,
    }
    
    logger.info(f"Dispatching job {job.job_id} to OCR engine at {settings.OCR_ENGINE_PROCESS_URL}")
    logger.debug(f"Dispatch payload: {payload}")

    try:
        resp = requests.post(
            settings.OCR_ENGINE_PROCESS_URL,
            json=payload,
            timeout=getattr(settings, "OCR_ENGINE_TIMEOUT_SECONDS", 30),
            headers = {
                "Authorization": settings.AI_ENGINE_API_KEY
            }
        )
        resp.raise_for_status()
        logger.info(f"OCR engine accepted job {job.job_id}, status_code={resp.status_code}")
    except (requests.Timeout, requests.ConnectionError) as e:
        logger.error(f"Connection/timeout error dispatching job {job.job_id}: {e}")
        raise OCRDispatchError(f"Dispatch connection/timeout error: {e}") from e
    except requests.HTTPError as e:
        logger.error(f"HTTP error dispatching job {job.job_id}: {e}, response={resp.text if 'resp' in locals() else 'N/A'}")
        raise OCRDispatchError(f"Dispatch HTTP error: {e}") from e
    except Exception as e:
        logger.exception(f"Unexpected error dispatching job {job.job_id}: {e}")
        raise OCRDispatchError(f"Dispatch unexpected error: {e}") from e