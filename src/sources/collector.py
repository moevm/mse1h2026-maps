import json
from typing import Any, Dict, List

from src.sources.open_alex import fetch_open_alex
from src.sources.wikidata import fetch_wikidata


def collect_all_sources(topic: str, request_id: int) -> List[Dict[str, Any]]:
    """
    Собирает данные из всех источников и сохраняет в SQL.
    Возвращает список сырых данных (словарей) для дальнейшей обработки.
    """

    open_alex_json = fetch_open_alex(topic)
    wikidata_json = fetch_wikidata(topic)

    with open("data.json", "w", encoding="utf-8") as write_file:
        json.dump(open_alex_json, write_file, indent=4, ensure_ascii=False)

    return [open_alex_json, wikidata_json]
