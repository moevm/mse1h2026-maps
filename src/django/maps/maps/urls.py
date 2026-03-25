from django.urls import path
from src.django.maps.example import views
from src.django.maps.mainapp import views as starter

urlpatterns = [
    path("test/", views.index),
    path("api/start/", starter.start),
    path("api/status/", starter.status),
    path("api/graph-widget/", starter.get_widget),
    path("api/node-info/", starter.node_info),
    path("", starter.home),
]
