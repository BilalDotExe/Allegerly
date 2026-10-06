from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_index, name="index"),
    path("sales/", views.sales_report, name="sales"),
    path("outstanding/", views.outstanding_report, name="outstanding"),
    path("stock/", views.stock_report, name="stock"),
    path("damages/", views.damages_report, name="damages"),
    path("returns/", views.returns_report, name="returns"),
    path("expiry/", views.expiry_report, name="expiry"),
    path("production/", views.production_report, name="production"),
]
