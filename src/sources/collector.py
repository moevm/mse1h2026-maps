from typing import Dict, Any, List
from wikidata import fetch_wikidata
from semantic_scholar import fetch_semantic_scholar


def collect_all_sources(topic: str, request_id: int) -> List[Dict[str, Any]]:
   """
   Собирает данные из всех источников и сохраняет в SQL.
   Возвращает список сырых данных (словарей) для дальнейшей обработки.
   """


   semantic_scholar_json = fetch_semantic_scholar(topic)
   wikidata_json = fetch_wikidata(topic)
  


   if wikidata_json:
       # Сохраняем в файл для просмотра
       import json
       with open('wikidata.json', 'w', encoding='utf-8') as f:
           json.dump(wikidata_json, f, indent=2, ensure_ascii=False)


   if semantic_scholar_json:
       # Сохраняем в файл для просмотра
       import json
       with open('semantic_scholar.json', 'w', encoding='utf-8') as f:
           json.dump(semantic_scholar_json, f, indent=2, ensure_ascii=False)