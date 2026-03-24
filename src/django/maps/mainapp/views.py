import os
import threading

from django.db import close_old_connections
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from neo4j import GraphDatabase

from src.db_access import get_request, put_request
from src.neo4j_db import set_to_neo4j, get_from_neo4j
from src.sources.collector import collect_all_sources


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
    VG = get_from_neo4j(driver, topic)
    driver.close()

    nodes = []
    for node in VG.nodes:
        nodes.append({
            "id": node.id,
            "caption": node.caption,  # или ":".join(node.properties["labels"])
            "labels": node.properties.get("labels", []),
            "properties": node.properties
        })

    relationships = []
    for rel in VG.relationships:
        relationships.append({
            "id": rel.id,
            "from": rel.source,
            "to": rel.target,
            "caption": rel.properties.get("type", ""),
            "properties": rel.properties
        })

    return JsonResponse({
        "nodes": nodes,
        "relationships": relationships
    })

    """for node in vg.nodes:
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

    widget = vg.render(
        layout=Layout.FORCE_DIRECTED,
        renderer="canvas",
        width="100%",
        height="600px")

    return JsonResponse({
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
