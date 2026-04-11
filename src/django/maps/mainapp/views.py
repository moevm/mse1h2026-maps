import os
import threading

from neo4j import GraphDatabase

from django.db import close_old_connections
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from src.db_access import get_request, put_request
from src.django.maps.mainapp.tasks import process_topic
from src.neo4j_db import get_from_neo4j, set_to_neo4j
from src.sources.collector import collect_all_sources


def home(request):
    return render(request, "index.html")


def logout(request):
    return render(request, "registration/logout.html")


def start(request):
    topic = request.GET.get("topic")

    req_id = put_request(topic)
    print(topic)
    process_topic.delay(req_id, topic)
    return HttpResponse(f"{req_id}")


def get_widget(request):
    request_id = request.GET.get("id")
    topic = get_request(request_id).topic

    uri = os.environ.get("NEO_URI")
    username = os.environ.get("NEO_USER")
    password = os.environ.get("NEO_PASSWORD")
    driver = GraphDatabase.driver(uri, auth=(username, password))
    VG = get_from_neo4j(driver, topic)
    driver.close()

    return JsonResponse(VG)


def node_info(request):
    node_id = request.GET.get("id")

    node_data = {
        "name": f"Узел {node_id}",
        "info": f"Подробная информация об узле {node_id}. Здесь могут быть любые данные из базы.",
        "links": [
            "Связанная сущность A",
            "Связанная сущность B",
            "Связанная сущность C",
        ],
        "resources": [
            {"name": "Википедия", "url": "https://ru.wikipedia.org"},
            {"name": "Официальный сайт", "url": "https://example.com"},
            {"name": "Документация", "url": "https://docs.example.com"},
        ],
    }

    return JsonResponse(node_data)


def status(request):
    id = request.GET.get("id")
    req = get_request(id)
    return HttpResponse(f"{req.status}")


def result(reqest):
    pass
