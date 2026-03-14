from django.http import HttpResponse
from django.shortcuts import render


def home(request):
    return render(request, 'index.html')


def start(reqest):
    topic = reqest.GET.get("topic")
    return HttpResponse(f"Topic added to queue: {topic}")
