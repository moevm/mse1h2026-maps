from typing import Any, Dict, List

from src.sources.semantic_scholar import fetch_semantic_scholar
from src.sources.wikidata import fetch_wikidata


def collect_all_sources(topic: str, request_id: int) -> List[Dict[str, Any]]:
    """
    Собирает данные из всех источников и сохраняет в SQL.
    Возвращает список сырых данных (словарей) для дальнейшей обработки.
    """

    semantic_scholar_json = fetch_semantic_scholar(topic)
    wikidata_json = fetch_wikidata(topic)

    return [semantic_scholar_json, wikidata_json]
