from django.urls import path

from example import views
from mainapp import views as starter

urlpatterns = [
    path('test/',views.index),
    path('api/start/', starter.start),
    path('',starter.home),
]
