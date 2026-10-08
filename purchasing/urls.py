from django.urls import path

from . import views

app_name = "purchasing"

urlpatterns = [
    path("", views.po_list, name="list"),
    path("create/", views.po_create, name="create"),
    path("<int:pk>/", views.po_detail, name="detail"),
    path("<int:pk>/edit/", views.po_edit, name="edit"),
    path("<int:pk>/place/", views.po_place, name="place"),
    path("<int:pk>/receive/", views.po_receive, name="receive"),
    path("<int:pk>/close/", views.po_close, name="close"),
    path("<int:pk>/cancel/", views.po_cancel, name="cancel"),
    path("<int:pk>/payment/", views.po_payment, name="payment"),
    path("<int:pk>/print/", views.po_print, name="print"),
]
