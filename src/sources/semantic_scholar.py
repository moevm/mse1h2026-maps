from typing import Dict, Any, List

def fetch_semantic_scholar(topic: str) -> List[Any]:
    """
    Получает данные из Semantic scholar по теме.
    Возвращает Сырую информацию:
        source: "semantic_scholar"
        id: "Q-1923"
        ...
    """