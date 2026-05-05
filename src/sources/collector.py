from typing import Any, Dict, List

from src.sources.github import fetch_github
from src.sources.open_alex import fetch_open_alex
from src.sources.wikidata import fetch_wikidata
from src.sources.wikipedia import fetch_wikipedia

simple_tasks = {
    "wikidata": fetch_wikidata,
}

complex_task = {
    "alex": fetch_open_alex,
    "github": fetch_github,
    "wikipedia": fetch_wikipedia,
}


def collect_all_sources(topic: str, request_id: int) -> List[Dict[str, Any]]:
    """
    Собирает данные из всех источников и сохраняет в SQL.
    Возвращает список сырых данных (словарей) для дальнейшей обработки.
    """

    open_alex_json = fetch_open_alex(topic)
    wikidata_json = fetch_wikidata(topic)
    wikipedia_json = fetch_wikipedia(topic)
    github_json = fetch_github(topic)

    return [[wikidata_json], [open_alex_json, wikipedia_json, github_json]]
