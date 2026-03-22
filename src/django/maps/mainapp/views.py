import threading

from neo4j import GraphDatabase

from django.db import close_old_connections
from django.http import HttpResponse
from django.shortcuts import render
from src.db_access import get_request, put_request
from src.from_neo4j import from_neo4j
from src.neo4j_db import set_to_neo4j
from src.sources.collector import collect_all_sources


def home(request):
    return render(request, "index.html")


def start(reqest):
    topic = reqest.GET.get("topic")
    print(topic)
    req_id = put_request(topic)

    # создать JSON файл и положить его в модель (БД)
    # в названии JSON можно добавить ID
    # использовать функцию Глеба
    # если возможно, то вернуть id сразу

    def task():
        close_old_connections()
        r = get_request(req_id)
        r.status = "processing"
        r.save()
        data = collect_all_sources(topic, req_id)[1]
        r.status = "completed"
        r.save()
        print(data)
        uri = "bolt://localhost:7687"
        username = "neo4j"
        password = "12345678"
        driver = GraphDatabase.driver(uri, auth=(username, password))
        set_to_neo4j(driver, data)
        mist = from_neo4j(driver)
        print(mist)
        driver.close()

    thread = threading.Thread(target=task)
    thread.daemon = True  # поток завершится при остановке основного процесса
    thread.start()
    # Вызвать функцию Кати
    return HttpResponse(f"{req_id}")


def status(reqest):
    id = reqest.GET.get("id")
    req = get_request(id)
    return HttpResponse(f"{req.status}")


def result(reqest):
    pass
