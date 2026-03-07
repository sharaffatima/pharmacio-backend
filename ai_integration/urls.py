from django.urls import path
from ai_integration.views import OCRResultCallbackView, OCRJobStatusView, ManualDispatchView

urlpatterns = [
    # Callback endpoint for OCR engine to post results
    path("ocr/result/", OCRResultCallbackView.as_view(), name="ocr-result-callback"),
    
    # Endpoint to check OCR job status
    path("ocr/job/<uuid:job_id>/", OCRJobStatusView.as_view(), name="ocr-job-status"),

    # Admin endpoint to manually trigger OCR job dispatch (for testing)
    path("ocr/job/<uuid:job_id>/dispatch/", ManualDispatchView.as_view(), name="manual-dispatch"),
    
]
