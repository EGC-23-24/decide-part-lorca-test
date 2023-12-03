from django.urls import path
from . import views

urlpatterns = [
    path("", views.configurator, name="configurator"),
    path("create_classic/", views.CreateClassicView.as_view(), name="create_classic"),
]
