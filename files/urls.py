from django.urls import path
from .views import FileUploadView, UploadStatusView

urlpatterns = [
    path('offers/upload/', FileUploadView.as_view(), name='file-upload'),
    path('offers/uploads/<uuid:id>/status/',
         UploadStatusView.as_view(), name='upload-status'),
]
