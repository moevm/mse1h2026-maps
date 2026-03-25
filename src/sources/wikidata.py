from typing import Any, Dict, List

import requests


def get_entity_id_by_label(
    label: str,
    lang: str = "en",
    url: str = "https://www.wikidata.org/w/api.php",
    headers={"User-Agent": "Mse1h2026-maps"},
) -> str:
    """Ищет QID по текстовому названию."""
    params = {
        "action": "wbsearchentities",
        "search": label,
        "language": lang,
        "format": "json",
    }
    response = requests.get(url, params=params, headers=headers).json()
    results = response.get("search", [])
    return results[0].get("id") if results else None


def collect_ids(data: any) -> set:
    """Рекурсивно собирает все Q-коды и P-коды из JSON-структуры."""
    found_ids = set()

    if isinstance(data, dict):
        # Проверяем структуру ссылок Wikidata
        if data.get("entity-type") == "item" and "id" in data:
            found_ids.add(data["id"])
        if "property" in data:
            found_ids.add(data["property"])

        # Рекурсивно заходим во все значения словаря
        for value in data.values():
            found_ids.update(collect_ids(value))

    elif isinstance(data, list):
        for item in data:
            found_ids.update(collect_ids(item))

    elif isinstance(data, str):
        # Проверка на отдельно стоящие ID типа 'Q123' или 'P123'
        if data.startswith(("Q", "P")) and data[1:].isdigit():
            found_ids.add(data)

    return found_ids


def fetch_labels_map(
    ids: set,
    lang: str = "en",
    url: str = "https://www.wikidata.org/w/api.php",
    headers={"User-Agent": "Mse1h2026-maps"},
) -> dict:
    """Загружает метки для всех ID пачками по 50 штук за один запрос."""
    labels_map = {}
    ids_list = list(ids)

    for i in range(0, len(ids_list), 50):
        batch = ids_list[i : i + 50]
        params = {
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": "labels",
            "languages": lang,
            "format": "json",
        }

        response = requests.get(url, params=params, headers=headers).json()
        entities = response.get("entities", {})

        for eid, content in entities.items():
            labels = content.get("labels", {})
            # Берем целевой язык, иначе английский, иначе сам ID
            label_val = labels.get(lang, labels.get("en", {})).get("value", eid)
            labels_map[eid] = label_val

    return labels_map


def enrich_structure(data: any, labels: dict) -> any:
    """Заменяет ID на словари с метками и ссылками."""
    if isinstance(data, dict):
        # Сначала обрабатываем вложенные элементы
        new_dict = {k: enrich_structure(v, labels) for k, v in data.items()}

        # Если это сущность (Q-код)
        if data.get("entity-type") == "item" and "id" in data:
            qid = data["id"]
            return {
                "id": qid,
                "label": labels.get(qid, qid),
                "url": f"https://www.wikidata.org/wiki/{qid}",
            }

        # Если это свойство (P-код)
        if "property" in data:
            pid = data["property"]
            new_dict["property_label"] = labels.get(pid, pid)
            new_dict["property_url"] = f"https://www.wikidata.org/wiki/Property:{pid}"

        return new_dict

    if isinstance(data, list):
        return [enrich_structure(item, labels) for item in data]

    if isinstance(data, str) and data.startswith(("Q", "P")) and data[1:].isdigit():
        return {
            "id": data,
            "label": labels.get(data, data),
            "url": f"https://www.wikidata.org/wiki/{data}",
        }

    return data


def transform_to_neo4j_format(wikidata_data: dict, query: str) -> dict:
    """
    Трансформирует обогащенный JSON из Wikidata в формат для загрузки в Neo4j.
    """
    nodes = []
    relationships = []
    # Извлекаем основную сущность из ответа (обычно это первый ключ в 'entities')
    entity_id = list(wikidata_data.get("entities", {}).keys())[0]
    entity = wikidata_data["entities"][entity_id]

    # 1. Создаем центральный узел (на основе искомой сущности)
    main_node_uid = f"wikidata:{entity_id}"
    main_node = {
        "uid": main_node_uid,
        "labels": ["Entity", "Concept"],  # Базовые лейблы по спецификации
        "properties": {
            "label_en": entity.get("labels", {}).get("en", {}).get("value"),
            "label_ru": entity.get("labels", {}).get("ru", {}).get("value"),
            "desc_en": entity.get("descriptions", {}).get("en", {}).get("value"),
            "wiki_url": f"https://www.wikidata.org/wiki/{entity_id}",
        },
    }
    nodes.append(main_node)

    # 2. Обрабатываем утверждения (claims) для создания связей и соседних узлов
    claims = entity.get("claims", {})
    for prop_id, statements in claims.items():
        for statement in statements:
            mainsnak = statement.get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})

            # Нас интересуют только связи с другими сущностями (Q-кодами)
            if datavalue.get("type") == "wikibase-entityid":
                target_id = datavalue["value"]["id"]
                target_uid = f"wikidata:{target_id}"

                # Извлекаем метку из обогащенных данных
                prop_label = mainsnak.get("property_label", prop_id)
                target_label = datavalue["value"].get("label", target_id)

                # Создаем тип связи (ЗАГЛАВНЫМИ, через подчеркивание) [cite: 69]
                rel_type = prop_label.upper().replace(" ", "_")

                # Добавляем целевой узел, если его еще нет
                nodes.append(
                    {
                        "uid": target_uid,
                        "labels": ["Entity", "Concept"],
                        "properties": {"label_en": target_label},
                    }
                )

                # Добавляем связь [cite: 26]
                relationships.append(
                    {
                        "from_uid": main_node_uid,
                        "to_uid": target_uid,
                        "type": rel_type,
                        "properties": {},  # Обязательно передаем пустой объект
                    }
                )

    return {
        "query": query,
        "sources": ["wikidata"],  # Список реально использованных источников [cite: 72]
        "nodes": nodes,
        "relationships": relationships,
    }


def fetch_wikidata(topic: str) -> List[Any]:
    """
    Получает данные из Wikidata по теме.
    Возвращает Сырую информацию:
        source: "wikidata"
        id: "Q-1922"
        ...
    """

    qid = get_entity_id_by_label(topic)
    if not qid:
        return None

    headers = {"User-Agent": "Mse1h2026-maps"}

    # Получаем основные данные сущности
    entity_url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    raw_data = requests.get(entity_url, headers=headers).json()

    # 1. Собираем все уникальные ID
    all_ids = collect_ids(raw_data)

    # 2. Предзагружаем все имена (batch-запрос)
    labels_dictionary = fetch_labels_map(all_ids)

    # 3. Трансформируем структуру
    result = enrich_structure(raw_data, labels_dictionary)
    return transform_to_neo4j_format(result, topic)
