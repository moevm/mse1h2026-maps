import requests
from math import ceil

HEADERS = {"User-Agent": "Mse1h2026-maps"}

def get_links_descriptions(links_titles: list, lang: str = "en"):

    links = {}

    batch_size = 50
    num_batches = ceil(len(links_titles) / batch_size)


    for i in range(num_batches):

        start = i * batch_size
        end = min((i + 1) * batch_size, len(links_titles))  # не выходим за пределы
        
        batch = links_titles[start:end]
        
        # Пропускаем пустые пачки
        if not batch:
            continue
        
        titles_pipe = "|".join([title.replace(" ", "_") for title in batch])

        params = {
            "action": "query",
            "titles": titles_pipe,    
            "prop": "extracts",
            "exintro": False,
            "explaintext": True,
            "format": "json"
        }

        url = f"https://{lang}.wikipedia.org/w/api.php"

        response = requests.get(url, headers=HEADERS, params=params)
        data = response.json()

        for link_name, value in data["query"]["pages"].items():
            if value.get("extract", "") != "":
                links[link_name] = value
    return links

def fetch_wikipedia(title: str, lang: str = "en",  limit: int = 150):
    """
    Возвращает краткое изложение статьи (первые абзацы).
    """
    url = "https://{}.wikipedia.org/w/api.php".format(lang)
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts|links",
        "exintro": False,
        "explaintext": True,
        "exsectionformat": "raw",
        "pllimit": limit, # лимит для links
        "format": "json"
    }
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        data = response.json()

        links_titles = []


        for link in list(data["query"]["pages"].values())[0]["links"]:
            if link.get("ns", "") == 0:
                links_titles.append(link["title"])

        list(data["query"]["pages"].values())[0]["links"] = get_links_descriptions(links_titles)

        return data
    except Exception as e:
        print(f"[Wikipedia] критическая ошибка {e}")
        return {}