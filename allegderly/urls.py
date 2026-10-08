"""
URL configuration for allegderly project.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('customers/', include('customers.urls')),
    path('vendors/', include('vendors.urls')),
    path('purchasing/', include('purchasing.urls')),
    path('inventory/', include('inventory.urls')),
    path("invoices/", include("invoices.urls")),
    path("damages/", include("damages.urls")),
    path("returns/", include("returns.urls")),
    path("production/", include("production.urls")),
    path("audit/", include("audit.urls")),
    path("reports/", include("reports.urls")),
]
