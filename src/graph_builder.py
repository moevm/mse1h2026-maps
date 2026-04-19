import json
import re
from typing import Any, Dict, List, Optional, Union

import matplotlib.pyplot as plt
import networkx as nx
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


def restore_abstract_from_inverted_index(inverted_index: dict) -> str:
    """Преобразует abstract_inverted_index OpenAlex в текст."""
    if not inverted_index or not isinstance(inverted_index, dict):
        return ""
    words = [
        word for idx, word in sorted(inverted_index.items(), key=lambda x: int(x[0]))
    ]
    return " ".join(words)


def detect_format(data: Union[Dict, List]) -> str:
    """Определяет формат входных данных: 'openalex' или 'wikidata'."""
    if isinstance(data, dict):
        if "results" in data and "meta" in data:
            return "openalex"
        if "nodes" in data and "relationships" in data:
            return "wikidata"
    return "unknown"


def extract_text_from_node(node: Dict[str, Any], source_format: str) -> str:
    """
    Извлекает текст для эмбеддинга из узла.
    Для OpenAlex: приоритет abstract > title.
    Для Wikidata: приоритет desc_en > label_en > label_ru > uid.
    """
    if source_format == "openalex":
        abstract = ""
        if "abstract_inverted_index" in node and node["abstract_inverted_index"]:
            abstract = restore_abstract_from_inverted_index(
                node["abstract_inverted_index"]
            )
        elif "abstract" in node and node["abstract"]:
            abstract = node["abstract"]
        title = node.get("title", "")
        return abstract if abstract else title
    elif source_format == "wikidata":
        props = node.get("properties", {})
        desc = props.get("desc_en", "") or node.get("descriptions", "")
        label = (
            props.get("label_en", "")
            or props.get("label_ru", "")
            or node.get("uid", "")
        )
        return desc if desc else label
    return ""


def collect_all_nodes(
    data: Union[Dict, List], expand_wikidata_children: bool = True
) -> List[Dict]:
    """
    Рекурсивно обходит входные данные и собирает все узлы в единый список.
    Каждый узел содержит: uid, text, original, source_type.
    """
    all_nodes = []
    fmt = detect_format(data)

    if fmt == "openalex":
        papers = data.get("results", [])
        for paper in papers:
            paper_id = paper.get("id", "")
            uid = (
                f"openalex:{paper_id}"
                if paper_id
                else f"openalex_unknown_{len(all_nodes)}"
            )
            text = extract_text_from_node(paper, "openalex")
            all_nodes.append(
                {"uid": uid, "text": text, "original": paper, "source_type": "openalex"}
            )
    elif fmt == "wikidata":
        nodes = data.get("nodes", [])
        relationships = data.get("relationships", [])
        node_dict = {node["uid"]: node for node in nodes}
        if expand_wikidata_children:
            for rel in relationships:
                for uid in (rel.get("from_uid"), rel.get("to_uid")):
                    if uid and uid not in node_dict:
                        node_dict[uid] = {
                            "uid": uid,
                            "labels": ["Entity"],
                            "properties": {"label_en": uid.split(":")[-1]},
                        }
        for uid, node in node_dict.items():
            text = extract_text_from_node(node, "wikidata")
            all_nodes.append(
                {"uid": uid, "text": text, "original": node, "source_type": "wikidata"}
            )
    elif isinstance(data, list):
        for item in data:
            all_nodes.extend(collect_all_nodes(item, expand_wikidata_children))
    return all_nodes


def collect_all_relationships(data: Union[Dict, List]) -> List[Dict]:
    """Собирает все явные связи из формата Wikidata."""
    relationships = []
    fmt = detect_format(data)
    if fmt == "wikidata":
        relationships.extend(data.get("relationships", []))
    elif isinstance(data, list):
        for item in data:
            relationships.extend(collect_all_relationships(item))
    return relationships


def build_similarity_graph_from_nodes(
    nodes: List[Dict],
    model_name: str = "all-mpnet-base-v2",
    threshold: float = 0.3,
) -> nx.Graph:
    """
    Строит граф схожести на основе эмбеддингов текстов узлов.
    Возвращает NetworkX граф, где у каждого узла есть атрибуты:
    uid, text, original, source_type.
    """
    texts = [node["text"] for node in nodes]
    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, convert_to_tensor=False)
    sim_matrix = cosine_similarity(embeddings)

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
    """Добавляет в граф явные связи из Wikidata"""
    uid_to_index = {
        G.nodes[idx].get("uid"): idx for idx in G.nodes() if G.nodes[idx].get("uid")
    }
    for rel in relationships:
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
        labels = ["Entity"]
        if attrs.get("source_type") == "openalex":
            labels.append("Paper")
        else:
            labels.append("Concept")

        properties = {}
        original = attrs.get("original", {})
        if attrs["source_type"] == "openalex":
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
        elif attrs["source_type"] in ("wikidata", "wikidata_explicit"):
            props = original.get("properties", {})
            properties = props.copy()
            if "label_en" not in properties and "label_en" in attrs:
                properties["label_en"] = attrs["label_en"]
            if "desc_en" not in properties and "desc_en" in attrs:
                properties["desc_en"] = attrs["desc_en"]
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


def build_graph_from_any(
    data: Union[Dict, List],
    query: str,
    sources: List[str],
    model_name: str = "all-mpnet-base-v2",
    threshold: float = 0.4,
    visualize: bool = False,
    expand_wikidata_children: bool = True,
) -> Dict[str, Any]:
    """
    Универсальная функция для OpenAlex и Wikidata.
    - Собирает все узлы.
    - Строит граф схожести на основе эмбеддингов
    (В качестве модели выбрана all-mpnet-base-v2, так как она показала
    лучшие результаты во время тестов)
    - Добавляет явные связи из Wikidata.
    - Возвращает JSON с узлами и отношениями.
    """
    all_nodes = collect_all_nodes(data, expand_wikidata_children)
    all_relationships = collect_all_relationships(data)

    if not all_nodes:
        return {"query": query, "sources": sources, "nodes": [], "relationships": []}

    G = build_similarity_graph_from_nodes(all_nodes, model_name, threshold)
    add_explicit_relationships(G, all_relationships)

    if visualize:
        visualize_combined_graph(G, title=f"Combined graph for '{query}'")

    return graph_to_output_dict(G, query, sources)


def visualize_combined_graph(
    G: nx.Graph, title: str = "Combined Graph", figsize=(14, 10)
):
    """Визуализация объединённого графа"""
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


# Пример использования
# if __name__ == "__main__":
#     with open("openalex.json", "r", encoding="utf-8") as f:
#         oa_data = json.load(f)
#     with open("wiki.json", "r", encoding="utf-8") as f:
#         wd_data = json.load(f)
#
#     result = build_graph_from_any(
#         [oa_data, wd_data],
#         query="Newton's method",
#         sources=["openalex", "wikidata"],
#         threshold=0.4,
#         visualize=True,
#         expand_wikidata_children=True
#     )
#     save_graph_to_json(result, "output_combined.json")
