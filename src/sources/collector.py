from typing import Any, Dict, List

from open_alex import fetch_open_alex
from wikidata import fetch_wikidata

import json

def collect_all_sources(topic: str, request_id: int) -> List[Dict[str, Any]]:
    """
    Собирает данные из всех источников и сохраняет в SQL.
    Возвращает список сырых данных (словарей) для дальнейшей обработки.
    """

    open_alex_json = fetch_open_alex(topic)
    wikidata_json = fetch_wikidata(topic)

    return [open_alex_json, wikidata_json]  
