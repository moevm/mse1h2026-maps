from django.http import HttpResponse
from django.shortcuts import render
from src.db_access import put_request, get_request


def home(request):
    return render(request, 'index.html')


def start(reqest):
    topic = reqest.GET.get("topic")
    req_id = put_request(topic)
    # создать JSON файл и положить его в модель (БД)
    # в названии JSON можно добавить ID
    # использовать функцию Глеба
    # если возможно, то вернуть id сразу
    return HttpResponse(f"{req_id}")


def status(reqest):
    id = reqest.GET.get("id")
    req = get_request(id)
    return HttpResponse(f"{req.status}")


def result(reqest):
    pass
