# collector/tasks.py
import os

from celery import chord, group, shared_task
from celery.utils.log import get_task_logger
from mainapp.models import RawData
from neo4j import GraphDatabase

from django.db import close_old_connections, transaction
from src.db_access import get_request
from src.graph_builder import build_graph_from_any
from src.neo4j_db import set_to_neo4j
from src.sources.collector import complex_task, simple_tasks

logger = get_task_logger(__name__)


@shared_task
def get_widget_task(user_id, topic):
    from django.contrib.auth import get_user_model
    from src.neo4j_db import get_from_neo4j

    User = get_user_model()
    user = User.objects.get(id=user_id)

    username = f"user{user.id}"
    password_hash = user.password.split("$")[2]
    uri = os.environ.get("NEO_URI")

    driver = GraphDatabase.driver(uri, auth=(username, password_hash))
    VG = get_from_neo4j(driver, f"{username}db", topic)
    driver.close()
    # logger.exception(f"VG: {VG}")
    return VG


@shared_task(bind=True, max_retries=3)
def process_simple_task(self, req_id: int, topic: str, source_name: str):
    data = None
    try:
        data = simple_tasks[source_name](topic)
        # logger.exception(f"Дата {self.name}: {data}")

        with transaction.atomic():
            topic_request = get_request(req_id)
            RawData.objects.create(
                topic_request=topic_request, source=source_name, data=data
            )

        send_data.apply(args=[data, req_id])

        status = "Done"
    except Exception as e:
        logger.exception(f"Ошибка в задаче {self.name}: {e}")
        status = "Error"
    with transaction.atomic():
        topic_request = get_request(req_id)
        topic_request.source_info[source_name] = status
        topic_request.save(update_fields=["source_info"])

    if status == "Done":
        return data, source_name


@shared_task(bind=True, max_retries=3)
def process_complex_task(self, req_id: int, topic: str, source_name: str):
    data_raw = None

    try:
        data_raw = complex_task[source_name](topic)
        # logger.exception(f"Дата {self.name}: {data_raw}")
        raw_id = 0
        with transaction.atomic():
            topic_request = get_request(req_id)
            raw_id = RawData.objects.create(
                topic_request=topic_request, source=source_name, data=data_raw
            ).id
        data = build_graph_from_any(data_raw, topic, [source_name], threshold=0.9)
        # logger.exception(f"Дата {self.name}: {data}")

        with transaction.atomic():
            RawData.objects.filter(id=raw_id).update(data=data, refined=True)

        send_data.apply(args=[data, req_id])

        status = "Done"
    except Exception as e:
        logger.exception(f"Ошибка в задаче {self.name}: {e}")
        status = "Error"

    with transaction.atomic():
        topic_request = get_request(req_id)
        topic_request.source_info[source_name] = status
        topic_request.save(update_fields=["source_info"])

    if status == "Done":
        return data_raw, source_name


@shared_task
def send_data(data, req_id: int):
    uri = os.environ.get("NEO_URI")
    req = get_request(req_id)
    username = f"user{req.author.id}"
    password = req.author.password.split("$")[2]
    driver = GraphDatabase.driver(uri, auth=(username, password))
    # logger.exception(f"DATA: {data}")
    set_to_neo4j(driver, f"{username}db", data)
    driver.close()


@shared_task
def finalize_topic(results, req_id):
    close_old_connections()
    """with transaction.atomic():
        r = get_request(req_id)
        r.status = "unpolished"
        r.save()"""

    topic = get_request(req_id).topic
    data_raw = []
    sources = []

    for elem in results:
        if elem is None:
            continue
        data_raw.append(elem[0])
        sources.append(elem[1])

    logger.exception(f"data size: {len(data_raw)} | src size: {len(sources)}")
    data = build_graph_from_any(data_raw, topic, sources, threshold=0.9)
    with transaction.atomic():
        topic_request = get_request(req_id)
        RawData.objects.create(
            topic_request=topic_request, source="ALL_SRC_DONE", data=data_raw
        )
    send_data.apply(args=[data, req_id])
    # time.sleep(2)
    with transaction.atomic():
        r = get_request(req_id)
        r.status = "completed"
        r.save()
    logger.info(f"Topic {req_id} completed")


@shared_task(bind=True, max_retries=3)
def process_topic(self, req_id: int, topic: str):
    close_old_connections()
    with transaction.atomic():
        r = get_request(req_id)
        r.status = "processing"
        r.save()

    simple = [
        process_simple_task.s(req_id, topic, name) for name in simple_tasks.keys()
    ]
    complex = [
        process_complex_task.s(req_id, topic, name) for name in complex_task.keys()
    ]
    all_tasks = simple + complex

    chord(group(all_tasks))(finalize_topic.s(req_id))
