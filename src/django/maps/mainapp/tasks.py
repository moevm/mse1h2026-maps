# collector/tasks.py
import os

from celery import shared_task
from neo4j import GraphDatabase

from django.db import close_old_connections
from src.db_access import get_request
from src.neo4j_db import set_to_neo4j
from src.sources.collector import collect_all_sources


@shared_task(bind=True, max_retries=3)
def process_topic(self, req_id: int, topic: str):
    print("TES")
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
