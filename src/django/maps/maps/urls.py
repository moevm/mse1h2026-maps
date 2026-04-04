from django.contrib import admin
from django.urls import include, path
from src.django.maps.example import views
from src.django.maps.mainapp import views as starter

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("test/", views.index),
    path("api/start/", starter.start),
    path("api/status/", starter.status),
    path("api/graph-widget/", starter.get_widget),
    path("api/node-info/", starter.node_info),
    path("logout/", starter.logout),
    path("", starter.home),
]
