from typing import Any, Dict, List

import cloudscraper
import requests

REQUEST_LIMIT = 50
MAX_TO_KEEP = 10


def get_full_abstract_unpaywall(doi, email="glebkhorchev@gmail.com"):
    """
    Запрашивает данные у Unpaywall по DOI, если основной источник не дал абстракт.
    """
    if not doi:
        return None

    # Unpaywall API требует email для идентификации пользователя
    url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
    try:
        # Unpaywall обычно не блокирует простые запросы так жестко, как S2
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("abstract")
    except Exception:
        return None
    return None


def fetch_semantic_scholar(topic: str) -> List[Any]:
    """
    Получает данные из Semantic scholar по теме.
    Возвращает Сырую информацию:
        source: "semantic_scholar"
        id: "Q-1923"
        ...
    """

    search_url = "https://api.semanticscholar.org/graph/v1/paper/search"

    # Настройка скрейпера для имитации реального браузера
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}, delay=15
    )

    params = {
        "query": topic,
        "limit": REQUEST_LIMIT,
        "fields": "title,abstract,year,authors,citationCount,externalIds,url",
    }

    try:

        response = scraper.get(search_url, params=params, proxies=None, timeout=35)

        if response.status_code != 200:
            print(f"Ошибка S2: {response.status_code}")
            return []

        raw_data = response.json().get("data", [])
        final_papers = []

        for item in raw_data:
            abstract = item.get("abstract")
            doi = item.get("externalIds", {}).get("DOI")

            # Если абстракт пустой или содержит заглушку, пробуем Unpaywall
            if not abstract or "elided by the publisher" in abstract.lower():
                recovered_abstract = get_full_abstract_unpaywall(doi)
                if recovered_abstract:
                    item["abstract"] = recovered_abstract
                    abstract = recovered_abstract

            # Добавляем в список только если абстракт теперь есть
            if abstract and "elided" not in abstract.lower():
                final_papers.append(item)

            if len(final_papers) >= MAX_TO_KEEP:
                break

        return final_papers

    except Exception as e:
        print(f"Критическая ошибка: {e}")
        return []
