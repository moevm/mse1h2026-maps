# collector/tasks.py
import datetime
import os
import time

from celery import chord, group, shared_task
from celery.utils.log import get_task_logger
from neo4j import GraphDatabase

from django.db import close_old_connections, transaction
from src.db_access import get_request
from src.graph_builder import build_graph
from src.neo4j_db import set_to_neo4j
from src.sources.collector import complex_task, simple_tasks

logger = get_task_logger(__name__)


@shared_task
def example1():
    print(f"EX1 - begin")
    time.sleep(2)
    print(f"EX1 - aftersleep")
    example2.delay()
    print("EX1 - can act")


@shared_task
def example2():
    print(f"EX2 - begin")
    time.sleep(4)
    print(f"EX2 - aftersleep")


@shared_task(bind=True, max_retries=3)
def process_simple_task(self, req_id: int, topic: str, source_name: str):
    try:
        data = simple_tasks[source_name](topic)
        # logger.exception(f"Дата {self.name}: {data}")

        uri = os.environ.get("NEO_URI")
        username = os.environ.get("NEO_USER")
        password = os.environ.get("NEO_PASSWORD")
        driver = GraphDatabase.driver(uri, auth=(username, password))

        set_to_neo4j(driver, data)
        driver.close()

        status = "Done"
    except Exception as e:
        logger.exception(f"Ошибка в задаче {self.name}: {e}")
        status = "Error"
    with transaction.atomic():
        topic_request = get_request(req_id)
        topic_request.source_info[source_name] = status
        topic_request.save(update_fields=["source_info"])


@shared_task(bind=True, max_retries=3)
def process_complex_task(self, req_id: int, topic: str, source_name: str):
    try:
        data = complex_task[source_name](topic)
        # logger.exception(f"Дата {self.name}: {data}")

        uri = os.environ.get("NEO_URI")
        username = os.environ.get("NEO_USER")
        password = os.environ.get("NEO_PASSWORD")
        driver = GraphDatabase.driver(uri, auth=(username, password))

        data = build_graph(data["results"], topic, ["openalex"], threshold=0.01)
        set_to_neo4j(driver, data)
        driver.close()

        status = "Done"
    except Exception as e:
        logger.exception(f"Ошибка в задаче {self.name}: {e}")
        status = "Error"

    with transaction.atomic():
        topic_request = get_request(req_id)
        topic_request.source_info[source_name] = status
        topic_request.save(update_fields=["source_info"])


@shared_task
def finalize_topic(results, req_id):
    close_old_connections()
    with transaction.atomic():
        r = get_request(req_id)
        r.status = "completed"
        r.save()
    logger.info(f"Topic {req_id} completed")


@shared_task(bind=True, max_retries=3)
def process_topic(self, req_id: int, topic: str):
    close_old_connections()
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
