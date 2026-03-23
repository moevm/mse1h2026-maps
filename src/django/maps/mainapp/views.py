import threading

from neo4j import GraphDatabase
import os

from django.db import close_old_connections
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from neo4j_viz import Layout
from neo4j_viz.colors import ColorSpace

from src.db_access import get_request, put_request
from src.neo4j_db import set_to_neo4j, get_from_neo4j
from src.sources.collector import collect_all_sources

import json


def home(request):
    return render(request, "index.html")


def start(request):
    topic = request.GET.get("topic")
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
        _, data = collect_all_sources(topic, req_id)


        print(data)
        uri = os.environ.get("NEO_URI")
        username = os.environ.get("NEO_USER")
        password = os.environ.get("NEO_PASSWORD")
        driver = GraphDatabase.driver(uri, auth=(username, password))

        set_to_neo4j(driver, data)

        with open("json/graph_example.json", "r", encoding="utf-8") as f:
            data2 = json.load(f)

        set_to_neo4j(driver, data2)

        driver.close()

        r.status = "completed"
        r.save()

    thread = threading.Thread(target=task)
    thread.daemon = True  # поток завершится при остановке основного процесса
    thread.start()
    return HttpResponse(f"{req_id}")


def get_widget(request):
    request_id = request.GET.get('id')
    topic = get_request(request_id).topic

    uri = os.environ.get("NEO_URI")
    username = os.environ.get("NEO_USER")
    password = os.environ.get("NEO_PASSWORD")
    driver = GraphDatabase.driver(uri, auth=(username, password))
    vg = get_from_neo4j(driver, topic)
    driver.close()

    for node in vg.nodes:
        node.caption = node.properties.get("name", node.id)
        node.properties["panel_data"] = {
            "name": node.properties.get("name"),
            "info": node.properties.get("info", "Нет информации"),
            "links": node.properties.get("links", []),
            "resources": node.properties.get("resources", [])
        }

    for rel in vg.relationships:
        rel.caption = rel.properties.get("type", "связь")

    vg.color_nodes(property="name", color_space=ColorSpace.DISCRETE)

    """widget = vg.render_widget(
        layout=Layout.FORCE_DIRECTED,
        renderer="canvas",
        width="100%",
        height="600px"
    )"""

    widget = vg.render(
        layout=Layout.FORCE_DIRECTED,
        renderer="canvas",
        width="100%",
        height="600px")

    return JsonResponse({
        'nodes': vg.nodes,
        'relationships': vg.relationships
    })

    """return JsonResponse({
        'html': widget.data
    })"""


def node_info(request):
    node_id = request.GET.get('id')

    node_data = {
        "name": f"Узел {node_id}",
        "info": f"Подробная информация об узле {node_id}. Здесь могут быть любые данные из базы.",
        "links": ["Связанная сущность A", "Связанная сущность B", "Связанная сущность C"],
        "resources": [
            {"name": "Википедия", "url": "https://ru.wikipedia.org"},
            {"name": "Официальный сайт", "url": "https://example.com"},
            {"name": "Документация", "url": "https://docs.example.com"}
        ]
    }

    return JsonResponse(node_data)


def status(request):
    id = request.GET.get("id")
    req = get_request(id)
    return HttpResponse(f"{req.status}")


def result(reqest):
    pass
