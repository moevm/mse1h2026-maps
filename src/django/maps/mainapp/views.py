import os

from neo4j import GraphDatabase

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from src.db_access import get_request, put_request
from src.django.maps.mainapp.tasks import get_widget_task, process_topic
from src.neo4j_db import get_from_neo4j


def home(request):
    return render(request, "index.html")


@require_http_methods(["GET"])
@ensure_csrf_cookie
def user_status(request):
    if request.user.is_authenticated:
        return JsonResponse(
            {
                "is_authenticated": True,
                "username": request.user.username,
            }
        )
    else:
        print("no")
        return JsonResponse(
            {
                "is_authenticated": False,
                "username": None,
            }
        )


@login_required
def start(request):
    topic = request.GET.get("topic")

    req_id = put_request(topic, request.user.id)
    print(topic)

    process_topic.delay(req_id, topic)

    return HttpResponse(f"{req_id}")


@login_required
def get_widget(request):
    request_id = request.GET.get("id")
    topic = get_request(request_id).topic

    task = get_widget_task.apply(args=[request.user.id, topic])
    VG = task.get()
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
    res = {}
    res["Status"] = req.status
    res["Info"] = req.source_info
    return JsonResponse(res)
    # return HttpResponse(f"{req.status}")


from src.neo4j_db import create_user_and_db


@require_http_methods(["POST"])
@csrf_protect
def register_user(request):
    username = request.POST.get("username")
    password = request.POST.get("password")

    if not username or not password:
        return JsonResponse({"error": "Username and password are required"}, status=400)

    if User.objects.filter(username=username).exists():
        return JsonResponse({"error": "User already exists"}, status=400)

    try:
        user = User.objects.create_user(username=username, password=password)

        uri = os.environ.get("NEO_URI")
        usernameN = os.environ.get("NEO_USER")
        passwordN = os.environ.get("NEO_PASSWORD")
        driver = GraphDatabase.driver(uri, auth=(usernameN, passwordN))

        password_hash = user.password.split("$")[2]
        username = user.id
        print(password_hash)
        print(username)
        tmp = create_user_and_db(driver, username, password_hash)
        print(tmp)

        return JsonResponse({"message": "Registration successful"}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
