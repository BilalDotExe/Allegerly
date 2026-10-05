from django.urls import path

from . import views

app_name = "returns"

urlpatterns = [
    path("", views.return_list, name="list"),
    path("new/", views.return_create, name="create"),
]
