from typing import Dict, Any, List

def fetch_wikidata(topic: str) -> List[Any]:
    """
    Получает данные из Wikidata по теме.
    Возвращает Сырую информацию:
        source: "wikidata"
        id: "Q-1922"
        ...
    """