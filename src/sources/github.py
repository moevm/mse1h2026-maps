import requests

# Без токена (60 запросов/час)
headers = {
    "User-Agent": "Mse1h2026-maps",
    "Accept": "application/vnd.github.v3+json"
}


GITHUB_TOKEN = ""
headers = {
    "User-Agent": "Mse1h2026-maps",
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"token {GITHUB_TOKEN}"
}

def fetch_github(query, per_page=10):
    """Поиск репозиториев по тексту"""
    url = "https://api.github.com/search/repositories"
    params = {
        "q": f"topic:{query}",
        "sort": "stars",
        "order": "desc",
        "per_page": per_page
    }

    try:
    
        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        return [
            {
                "url": repo["html_url"],
                "description": repo["description"],
                "topics": repo["topics"],
                "language": repo["language"]
            }
            for repo in data.get("items", [])
        ]
    except Exception as e:
        print(f"[Github] критическая ошибка {e}")
        return {}