import requests
from django.conf import settings
from ai_integration.models import OCRJob

# Service module responsible for dispatching OCR jobs to the OCR engine and handling related errors.

class OCRDispatchError(Exception):
    pass


def dispatch_to_ocr_engine(*, job: OCRJob) -> None:
    """
    Sends {job_id, file_reference} to the OCR engine.
    Raises OCRDispatchError on failure.
    """
    payload = {
        "job_id": str(job.job_id),
        "file_reference": job.file.s3_key,
    }

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
    except (requests.Timeout, requests.ConnectionError) as e:
        raise OCRDispatchError(f"Dispatch connection/timeout error: {e}") from e
    except requests.HTTPError as e:
        raise OCRDispatchError(f"Dispatch HTTP error: {e}") from e
    except Exception as e:
        raise OCRDispatchError(f"Dispatch unexpected error: {e}") from e