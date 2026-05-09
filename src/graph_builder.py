import json
import re
from typing import Any, Dict, List, Optional, Union

import matplotlib.pyplot as plt
import networkx as nx
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


def restore_abstract_from_inverted_index(inverted_index: dict) -> str:
    if not inverted_index or not isinstance(inverted_index, dict):
        return ""
    words = [
        word for idx, word in sorted(inverted_index.items(), key=lambda x: int(x[0]))
    ]
    return " ".join(words)


def build_similarity_graph_from_nodes(
    nodes: List[Dict],
    model_name: str = "all-mpnet-base-v2",
    threshold: float = 0.3,
) -> nx.Graph:
    """
    Строит граф схожести на основе эмбеддингов текстов узлов.
    """
    if not nodes:
        raise ValueError(
            "GraphBuilder: список узлов пуст, невозможно построить граф схожести"
        )
    if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1:
        raise ValueError("GraphBuilder: threshold должен быть числом от 0 до 1")

    try:
        texts = [node["text"] for node in nodes]
        model = SentenceTransformer(model_name)
        embeddings = model.encode(texts, convert_to_tensor=False)
        sim_matrix = cosine_similarity(embeddings)
    except Exception as e:
        raise ValueError(f"GraphBuilder: ошибка при создании эмбеддингов: {str(e)}")

    G = nx.Graph()
    for i, node in enumerate(nodes):
        G.add_node(
            i,
            uid=node["uid"],
            text=node["text"],
            original=node["original"],
            source_type=node["source_type"],
        )
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            sim = sim_matrix[i][j]
            if sim >= threshold:
                G.add_edge(i, j, weight=float(sim), type="SIMILAR_TO")
    return G


def add_explicit_relationships(G: nx.Graph, relationships: List[Dict]):
    """
    Добавляет в граф явные связи (из Wikidata или Wikipedia).
    """
    uid_to_index = {
        G.nodes[idx].get("uid"): idx for idx in G.nodes() if G.nodes[idx].get("uid")
    }
    if not isinstance(relationships, list):
        raise ValueError("GraphBuilder: relationships должен быть списком")
    for rel in relationships:
        if not isinstance(rel, dict):
            continue
        from_uid = rel.get("from_uid")
        to_uid = rel.get("to_uid")
        if not from_uid or not to_uid:
            continue
        if from_uid not in uid_to_index:
            new_idx = len(G.nodes)
            G.add_node(
                new_idx,
                uid=from_uid,
                text="",
                original={},
                source_type="wikidata_explicit",
            )
            uid_to_index[from_uid] = new_idx
        if to_uid not in uid_to_index:
            new_idx = len(G.nodes)
            G.add_node(
                new_idx,
                uid=to_uid,
                text="",
                original={},
                source_type="wikidata_explicit",
            )
            uid_to_index[to_uid] = new_idx
        G.add_edge(
            uid_to_index[from_uid],
            uid_to_index[to_uid],
            type=rel.get("type", "UNKNOWN"),
            properties=rel.get("properties", {}),
        )


def graph_to_output_dict(G: nx.Graph, query: str, sources: List[str]) -> Dict[str, Any]:
    """Преобразует NetworkX граф в JSON-формат для neo4j"""
    nodes_out = []
    relationships_out = []

    for node_id, attrs in G.nodes(data=True):
        uid = attrs.get("uid", f"node_{node_id}")
        source_type = attrs.get("source_type", "")
        labels = ["Entity"]

        if source_type == "openalex":
            labels.append("Paper")
        elif source_type in ("wikidata", "wikidata_explicit"):
            labels.append("Concept")
        elif source_type == "github":
            labels.append("Repository")
        elif source_type == "wikipedia":
            labels.append("WikipediaPage")
        else:
            labels.append("Concept")

        properties = {}
        original = attrs.get("original", {})

        if source_type == "openalex":
            properties["label_en"] = original.get("title", "")
            year = None
            pub_date = original.get("publication_date")
            if pub_date:
                match = re.search(r"\d{4}", pub_date)
                if match:
                    year = int(match.group(0))
            if year:
                properties["year"] = year
            properties["abstract"] = attrs.get("text", "")
            properties["paperId"] = original.get("id", "")

        elif source_type in ("wikidata", "wikidata_explicit"):
            props = original.get("properties", {})
            properties = props.copy()
            if "label_en" not in properties and "label_en" in attrs:
                properties["label_en"] = attrs["label_en"]
            if "desc_en" not in properties and "desc_en" in attrs:
                properties["desc_en"] = attrs["desc_en"]

        elif source_type == "github":
            properties["label_en"] = original.get("description", "")[:200]
            properties["description"] = original.get("description", "")
            properties["url"] = original.get("url", "")
            properties["language"] = original.get("language", "")
            properties["topics"] = original.get("topics", [])

        elif source_type == "wikipedia":
            properties["label_en"] = original.get("title", "")
            properties["description"] = original.get("extract", "")[:500]
            properties["url"] = (
                f"https://en.wikipedia.org/?curid={original.get('pageid', '')}"
            )
            properties["pageid"] = original.get("pageid", None)

        nodes_out.append({"uid": uid, "labels": labels, "properties": properties})

    for u, v, edge_attrs in G.edges(data=True):
        from_uid = G.nodes[u].get("uid", f"node_{u}")
        to_uid = G.nodes[v].get("uid", f"node_{v}")
        rel_type = edge_attrs.get("type", "SIMILAR_TO")
        rel_props = edge_attrs.get("properties", {}).copy()
        if "weight" in edge_attrs and "similarity" not in rel_props:
            rel_props["similarity"] = round(edge_attrs["weight"], 3)
        relationships_out.append(
            {
                "from_uid": from_uid,
                "to_uid": to_uid,
                "type": rel_type,
                "properties": rel_props,
            }
        )

    return {
        "query": query,
        "sources": sources,
        "nodes": nodes_out,
        "relationships": relationships_out,
    }


def visualize_combined_graph(
    G: nx.Graph, title: str = "Combined Graph", figsize=(14, 10)
):
    plt.figure(figsize=figsize)
    pos = nx.spring_layout(G, k=0.5, seed=42)
    nx.draw_networkx_nodes(G, pos, node_color="lightblue", node_size=300)
    nx.draw_networkx_edges(G, pos, alpha=0.3, edge_color="gray")
    labels = {}
    for node in G.nodes(data=True):
        uid = node[1].get("uid", str(node[0]))
        original = node[1].get("original", {})
        if node[1].get("source_type") == "openalex":
            label = original.get("title", uid.split(":")[-1])
        else:
            props = original.get("properties", {})
            label = props.get("label_en") or props.get("desc_en") or uid.split(":")[-1]
        labels[node[0]] = label[:20]
    nx.draw_networkx_labels(G, pos, labels, font_size=7)
    plt.title(title)
    plt.axis("off")
    plt.tight_layout()
    plt.show()


def save_graph_to_json(graph_dict: Dict[str, Any], filename: str = "graph.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(graph_dict, f, indent=2, ensure_ascii=False)


def _openalex_extract_text(node: dict) -> str:
    abstract = ""
    if "abstract_inverted_index" in node and node["abstract_inverted_index"]:
        abstract = restore_abstract_from_inverted_index(node["abstract_inverted_index"])
    elif "abstract" in node and node["abstract"]:
        abstract = node["abstract"]
    title = node.get("title", "")
    return abstract if abstract else title


def _openalex_collect_nodes(data: dict, expand: bool = True) -> List[dict]:
    """Собирает узлы из OpenAlex JSON. Проверяет структуру."""
    if not isinstance(data, dict):
        raise ValueError("GraphBuilder: данные OpenAlex должны быть словарём")
    if "results" not in data or "meta" not in data:
        raise ValueError(
            "GraphBuilder: в данных OpenAlex отсутствуют ключи 'results' или 'meta'"
        )
    if not isinstance(data["results"], list):
        raise ValueError("GraphBuilder: 'results' должен быть списком")
    papers = data["results"]
    nodes = []
    for idx, paper in enumerate(papers):
        if not isinstance(paper, dict):
            raise ValueError(
                f"GraphBuilder: элемент 'results' под индексом {idx} не является словарём"
            )
        paper_id = paper.get("id", "")
        uid = f"openalex:{paper_id}" if paper_id else f"openalex_unknown_{len(nodes)}"
        text = _openalex_extract_text(paper)
        nodes.append(
            {"uid": uid, "text": text, "original": paper, "source_type": "openalex"}
        )
    return nodes


def _openalex_collect_relationships(data: dict) -> List[dict]:
    return []


def _wikidata_extract_text(node: dict) -> str:
    props = node.get("properties", {})
    desc = props.get("desc_en", "") or node.get("descriptions", "")
    label = (
        props.get("label_en", "") or props.get("label_ru", "") or node.get("uid", "")
    )
    return desc if desc else label


def _wikidata_collect_nodes(data: dict, expand: bool = True) -> List[dict]:
    """Собирает узлы Wikidata. Проверяет структуру."""
    if not isinstance(data, dict):
        raise ValueError("GraphBuilder: данные Wikidata должны быть словарём")
    if "nodes" not in data or "relationships" not in data:
        raise ValueError(
            "GraphBuilder: в данных Wikidata отсутствуют ключи 'nodes' или 'relationships'"
        )
    if not isinstance(data["nodes"], list):
        raise ValueError("GraphBuilder: 'nodes' должен быть списком")
    if not isinstance(data["relationships"], list):
        raise ValueError("GraphBuilder: 'relationships' должен быть списком")

    nodes = data["nodes"]
    relationships = data["relationships"]
    node_dict = {node["uid"]: node for node in nodes}
    if expand:
        for rel in relationships:
            for uid in (rel.get("from_uid"), rel.get("to_uid")):
                if uid and uid not in node_dict:
                    node_dict[uid] = {
                        "uid": uid,
                        "labels": ["Entity"],
                        "properties": {"label_en": uid.split(":")[-1]},
                    }
    result = []
    for uid, node in node_dict.items():
        text = _wikidata_extract_text(node)
        result.append(
            {"uid": uid, "text": text, "original": node, "source_type": "wikidata"}
        )
    return result


def _wikidata_collect_relationships(data: dict) -> List[dict]:
    return data.get("relationships", [])


def _github_matches(data) -> bool:
    """Список объектов с ключами 'url', 'description', 'topics'."""
    return (
        isinstance(data, list)
        and len(data) > 0
        and isinstance(data[0], dict)
        and all(k in data[0] for k in ["url", "description", "topics"])
    )


def _github_extract_text(node: dict) -> str:
    desc = node.get("description", "")
    topics = " ".join(node.get("topics", []))
    return f"{desc} {topics}"


def _github_collect_nodes(data: list, expand: bool = True) -> List[dict]:
    """Собирает узлы GitHub. Ожидает список словарей."""
    if not isinstance(data, list):
        raise ValueError("GraphBuilder: данные GitHub должны быть списком")
    if len(data) == 0:
        raise ValueError("GraphBuilder: список GitHub пуст")
    nodes = []
    for idx, repo in enumerate(data):
        if not isinstance(repo, dict):
            raise ValueError(
                f"GraphBuilder: элемент GitHub под индексом {idx} не является словарём"
            )
        if not all(k in repo for k in ["url", "description", "topics"]):
            raise ValueError(
                f"GraphBuilder: элемент GitHub под индексом {idx} не содержит обязательные ключи 'url', 'description', 'topics'"
            )
        url = repo.get("url", "")
        uid = f"github:{url}" if url else f"github_unknown_{len(nodes)}"
        text = _github_extract_text(repo)
        nodes.append(
            {"uid": uid, "text": text, "original": repo, "source_type": "github"}
        )
    return nodes


def _github_collect_relationships(data: dict) -> List[dict]:
    return []


def _wikipedia_matches(data) -> bool:
    return (
        isinstance(data, dict)
        and "query" in data
        and isinstance(data["query"], dict)
        and "pages" in data["query"]
    )


def _wikipedia_extract_text(node: dict) -> str:
    title = node.get("title", "")
    extract = node.get("extract", "")
    return f"{title} {extract}" if title or extract else ""


def _wikipedia_collect_nodes(data: dict, expand: bool = True) -> List[dict]:
    """Собирает узлы Wikipedia. Проверяет структуру."""
    if not isinstance(data, dict):
        raise ValueError("GraphBuilder: данные Wikipedia должны быть словарём")
    if "query" not in data or not isinstance(data["query"], dict):
        raise ValueError("GraphBuilder: отсутствует или повреждён ключ 'query'")
    if "pages" not in data["query"] or not isinstance(data["query"]["pages"], dict):
        raise ValueError("GraphBuilder: 'query.pages' должен быть непустым словарём")
    pages = data["query"]["pages"]
    if not pages:
        raise ValueError("GraphBuilder: словарь 'pages' пуст")

    nodes = []
    seen_uids = set()

    for pageid, page in pages.items():
        if not isinstance(page, dict):
            raise ValueError(
                f"GraphBuilder: страница {pageid} в Wikipedia должна быть словарём"
            )
        uid = f"wikipedia:{pageid}"
        text = _wikipedia_extract_text(page)
        nodes.append(
            {"uid": uid, "text": text, "original": page, "source_type": "wikipedia"}
        )
        seen_uids.add(uid)

    if not expand:
        return nodes

    for pageid, page in pages.items():
        links = page.get("links", {})
        if not isinstance(links, dict):
            continue
        for link_pageid, link_info in links.items():
            uid = f"wikipedia:{link_pageid}"
            if uid not in seen_uids:
                text = _wikipedia_extract_text(link_info)
                nodes.append(
                    {
                        "uid": uid,
                        "text": text,
                        "original": link_info,
                        "source_type": "wikipedia",
                    }
                )
                seen_uids.add(uid)
    return nodes


def _wikipedia_collect_relationships(data: dict) -> List[dict]:
    """Создаёт связи WIKI_LINK между страницами на основе поля links."""
    rels = []
    pages = data["query"]["pages"]
    for pageid, page in pages.items():
        from_uid = f"wikipedia:{pageid}"
        links = page.get("links", {})
        if not isinstance(links, dict):
            continue
        for link_pageid in links:
            to_uid = f"wikipedia:{link_pageid}"
            rels.append(
                {
                    "from_uid": from_uid,
                    "to_uid": to_uid,
                    "type": "WIKI_LINK",
                    "properties": {},
                }
            )
    return rels


FORMAT_REGISTRY = {
    "openalex": {
        "signature_keys": ["results", "meta"],
        "extract_text": _openalex_extract_text,
        "collect_nodes": _openalex_collect_nodes,
        "collect_relationships": _openalex_collect_relationships,
    },
    "wikidata": {
        "signature_keys": ["nodes", "relationships"],
        "extract_text": _wikidata_extract_text,
        "collect_nodes": _wikidata_collect_nodes,
        "collect_relationships": _wikidata_collect_relationships,
    },
    "github": {
        "matches": _github_matches,
        "extract_text": _github_extract_text,
        "collect_nodes": _github_collect_nodes,
        "collect_relationships": _github_collect_relationships,
    },
    "wikipedia": {
        "matches": _wikipedia_matches,
        "extract_text": _wikipedia_extract_text,
        "collect_nodes": _wikipedia_collect_nodes,
        "collect_relationships": _wikipedia_collect_relationships,
    },
}


def detect_format(data: Union[Dict, List]) -> Optional[str]:
    for fmt_name, cfg in FORMAT_REGISTRY.items():
        if "matches" in cfg:
            try:
                if cfg["matches"](data):
                    return fmt_name
            except Exception as e:
                continue
        elif "signature_keys" in cfg and isinstance(data, dict):
            if all(k in data for k in cfg["signature_keys"]):
                return fmt_name
    return None


def parse_any(data: Union[Dict, List], expand_wikidata_children: bool = True):
    """
    Анализирует структуру данных, определяет формат по реестру и извлекает
    все узлы и связи. Возвращает (all_nodes, all_relationships).
    """
    all_nodes = []
    all_relationships = []

    if isinstance(data, list):
        fmt = detect_format(data)
        if fmt:
            cfg = FORMAT_REGISTRY[fmt]
            try:
                nodes = cfg["collect_nodes"](data, expand_wikidata_children)
                all_nodes.extend(nodes)
                if "collect_relationships" in cfg:
                    rels = cfg["collect_relationships"](data)
                    all_relationships.extend(rels)
            except Exception as e:
                if str(e).startswith("GraphBuilder:"):
                    raise
                raise ValueError(
                    f"GraphBuilder: ошибка при обработке формата '{fmt}': {str(e)}"
                )
            return all_nodes, all_relationships
        for item in data:
            sub_nodes, sub_rels = parse_any(item, expand_wikidata_children)
            all_nodes.extend(sub_nodes)
            all_relationships.extend(sub_rels)
        return all_nodes, all_relationships

    fmt = detect_format(data)
    if not fmt:
        return all_nodes, all_relationships

    cfg = FORMAT_REGISTRY[fmt]
    try:
        nodes = cfg["collect_nodes"](data, expand_wikidata_children)
        all_nodes.extend(nodes)
        if "collect_relationships" in cfg:
            rels = cfg["collect_relationships"](data)
            all_relationships.extend(rels)
    except Exception as e:
        if str(e).startswith("GraphBuilder:"):
            raise
        raise ValueError(
            f"GraphBuilder: ошибка при обработке формата '{fmt}': {str(e)}"
        )

    return all_nodes, all_relationships


def build_graph_from_any(
    data: Union[Dict, List],
    query: str,
    sources: Optional[List[str]] = None,
    model_name: str = "all-mpnet-base-v2",
    threshold: float = 0.4,
    visualize: bool = False,
    expand_wikidata_children: bool = True,
) -> Dict[str, Any]:
    """
    Универсальная функция для зарегистрированных форматов.
    - Собирает все узлы.
    - Строит граф схожести на основе эмбеддингов.
    - Добавляет явные связи.
    - Возвращает JSON с узлами и отношениями.
    """
    try:
        all_nodes, all_relationships = parse_any(data, expand_wikidata_children)
    except Exception as e:
        if str(e).startswith("GraphBuilder:"):
            raise
        raise ValueError(f"GraphBuilder: ошибка при разборе входных данных: {str(e)}")

    if sources is None:
        source_types = set()
        for node in all_nodes:
            st = node.get("source_type", "")
            if st:
                if st == "wikidata_explicit":
                    source_types.add("wikidata")
                else:
                    source_types.add(st)
        sources = sorted(list(source_types))

    if not all_nodes:
        return {"query": query, "sources": sources, "nodes": [], "relationships": []}

    try:
        G = build_similarity_graph_from_nodes(all_nodes, model_name, threshold)
    except Exception as e:
        if str(e).startswith("GraphBuilder:"):
            raise
        raise ValueError(
            f"GraphBuilder: ошибка при построении графа схожести: {str(e)}"
        )

    try:
        add_explicit_relationships(G, all_relationships)
    except Exception as e:
        if str(e).startswith("GraphBuilder:"):
            raise
        raise ValueError(f"GraphBuilder: ошибка при добавлении явных связей: {str(e)}")

    if visualize:
        try:
            visualize_combined_graph(G, title=f"Combined graph for '{query}'")
        except Exception as e:
            raise ValueError(f"GraphBuilder: ошибка при визуализации графа: {str(e)}")

    try:
        return graph_to_output_dict(G, query, sources)
    except Exception as e:
        raise ValueError(
            f"GraphBuilder: ошибка при преобразовании графа в выходной формат: {str(e)}"
        )


# Пример использования

# if __name__ == "__main__":
#     try:
#         with open("openalex.json", "r", encoding="utf-8") as f:
#             oa_data = json.load(f)
#         with open("w1.json", "r", encoding="utf-8") as f:
#             wd_data = json.load(f)
#         with open("wiki.json", "r", encoding="utf-8") as f:
#             wd_data1 = json.load(f)
#         with open("github.json", "r", encoding="utf-8") as f:
#             github_data = json.load(f)
#
#         result = build_graph_from_any(
#             [oa_data, github_data, wd_data1],
#             query="Newton's method",
#             threshold=0.4,
#             visualize=True,
#             expand_wikidata_children=True
#         )
#         save_graph_to_json(result, "output_combined.json")
#     except Exception as e:
#         print(f"GraphBuilder: общая ошибка выполнения: {e}")
