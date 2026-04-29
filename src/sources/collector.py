import json
from typing import Any, Dict, List

from src.sources.open_alex import fetch_open_alex
from src.sources.wikidata import fetch_wikidata

simple_tasks = {
    "wikidata": fetch_wikidata,
}

complex_task = {"alex": fetch_open_alex}


def collect_all_sources(topic: str, request_id: int) -> List[Dict[str, Any]]:
    """
    Собирает данные из всех источников и сохраняет в SQL.
    Возвращает список сырых данных (словарей) для дальнейшей обработки.
    """

    open_alex_json = fetch_open_alex(topic)
    wikidata_json = fetch_wikidata(topic)

    return [[open_alex_json], [wikidata_json]]
