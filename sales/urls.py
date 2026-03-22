from django.urls import path

from sales.views import SaleCreateView


urlpatterns = [
    path("sales", SaleCreateView.as_view(), name="sales-create-no-slash"),
    path("sales/", SaleCreateView.as_view(), name="sales-create"),
]
