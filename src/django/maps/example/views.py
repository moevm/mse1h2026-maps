from django.contrib.auth.models import User
from django.http import HttpResponse
from src.django.maps.mainapp import tasks


def index(request):
    tasks.example1.delay()
    return HttpResponse("PLACEHOLDER")
