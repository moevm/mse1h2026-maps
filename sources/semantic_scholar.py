from typing import Dict, Any

def fetch_semantic_scholar(topic: str) -> Dict[str, Any]:
    """
    Получает данные из Semantic scholar по теме.
    Возвращает словарь с ключами:
        source: "semantic_scholar"
        entities: список сущностей (id, name, type, description)
        relations: список связей (from, to, type)
    """