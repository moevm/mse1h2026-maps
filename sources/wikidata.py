from typing import Dict, Any

def fetch_wikidata(topic: str) -> Dict[str, Any]:
    """
    Получает данные из Wikidata по теме.
    Возвращает словарь с ключами:
        source: "wikidata"
        entities: список сущностей (id, name, type, description)
        relations: список связей (from, to, type)
    """