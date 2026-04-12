import requests
import json

def decode_inverted_abstract(inverted_index: dict) -> str:
    """Превращает словарь {позиция: [слова]} в обычный текст."""
    if not inverted_index:
        return ""
    
    max_index = 0

    for value in inverted_index.values():
        for pos in value:
            if pos > max_index:
                max_index = pos
    
    words = [None] * (max_index + 1)

    for word, positions in inverted_index.items():
        for p in positions:
            words[p] = word
    # Объединяем, заменяя None на пустую строку
    return " ".join(word if word is not None else "" for word in words)

def fetch_open_alex(topic: str):

    url = "https://api.openalex.org/works"
    params = {
        "search" : topic,
        "per_page": 30,
        "select": "id, title, primary_location, publication_date, doi, abstract_inverted_index"
    }

    headers = {"User-Agent": "Mse1h2026-maps"}

    try:

        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code != 200:
                print(f"[OpenAlex] Ошибка сервера: {response.status_code}")
                return []
        data = response.json()
        works_with_full_abstract = []
        for result in data["results"]:
            if (result["abstract_inverted_index"] != None):
                result["abstract_inverted_index"] = decode_inverted_abstract(result["abstract_inverted_index"])
                works_with_full_abstract.append(result)

        data["results"] = works_with_full_abstract
        return data

    except Exception as e:
        print(f"[OpenAlex] Критическая ошибка: {e}")
        return []

