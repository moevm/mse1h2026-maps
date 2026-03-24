import json
from typing import List, Dict, Any, Optional

import matplotlib.pyplot as plt
import networkx as nx
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


def load_papers_from_json(json_path: str) -> List[Dict[str, Any]]:
    with open(json_path, "r", encoding="utf-8") as f:
        papers = json.load(f)
    return papers


def preprocess_text(text: Optional[str]) -> str:
    if text is None or text.strip() == "":
        return ""
    return text.strip()

# Алгоритм основан не ембеддинге(embedding)
# Готовые модели преобразуют описание статей в вектора
# Близость статей сравнивается с использованием косинусоидальной меры


# all-mpnet-base-v2 (Показывает хорошие результаты, но работает не слишком быстро)
# all-MiniLM-L6-v2 (Удовлетворительные результаты и быстрая скорость)
# allenai-specter 


def build_similarity_graph(
    papers: List[Dict[str, Any]],
    model_name: str = "all-mpnet-base-v2",
    threshold: float = 0.3
) -> nx.Graph:
    abstracts = [preprocess_text(p.get("abstract", "")) for p in papers]

    model = SentenceTransformer(model_name)
    embeddings = model.encode(abstracts, convert_to_tensor=False)
    sim_matrix = cosine_similarity(embeddings)

    G = nx.Graph()
    for i, paper in enumerate(papers):
        G.add_node(
            i,
            title=paper.get("title", ""),
            year=paper.get("year", ""),
            paperId=paper.get("paperId", ""),
        )

    for i in range(len(papers)):
        for j in range(i + 1, len(papers)):
            sim = sim_matrix[i][j]
            if sim >= threshold:
                G.add_edge(i, j, weight=float(sim))

    return G


def visualize_graph(G: nx.Graph, papers: List[Dict[str, Any]], figsize=(12, 8)):
    plt.figure(figsize=figsize)
    pos = nx.spring_layout(G, k=1, seed=42)

    nx.draw_networkx_nodes(G, pos, node_color="lightblue", node_size=500)

    edges = G.edges(data=True)
    weights = [d["weight"] * 2 for _, _, d in edges]
    nx.draw_networkx_edges(
        G, pos, edgelist=edges, width=weights, alpha=0.6, edge_color="gray"
    )

    labels = {i: f"{papers[i].get('title', 'No title')[:30]}..." for i in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, font_size=8)

    plt.title("")
    plt.axis("off")
    plt.tight_layout()
    plt.show()


def create_graph_dict(
    G: nx.Graph,
    papers: List[Dict[str, Any]],
    query: str,
    sources: List[str]
) -> Dict[str, Any]:
    nodes = []
    relationships = []
    uid_map = {}

    for i, paper in enumerate(papers):
        paper_id = paper.get("paperId", f"unknown_{i}")
        uid = f"semanticscholar:{paper_id}"
        uid_map[i] = uid

        title = paper.get("title", "")
        year = paper.get("year")
        citation_count = paper.get("citationCount", 0)
        external_ids = paper.get("externalIds", {})
        doi = external_ids.get("DOI", "")

        authors_list = paper.get("authors", [])
        authors_names = [a.get("name", "") for a in authors_list if isinstance(a, dict)]
        authors_str = ", ".join(authors_names) if authors_names else ""

        abstract = paper.get("abstract", "")

        properties = {"label_en": title}
        if year:
            properties["year"] = year
        if citation_count:
            properties["citations"] = citation_count
        if doi:
            properties["doi"] = doi
        if authors_str:
            properties["authors"] = authors_str
        if abstract:
            properties["abstract"] = abstract

        nodes.append({"uid": uid, "labels": ["Entity", "Paper"], "properties": properties})

    for u, v, data in G.edges(data=True):
        weight = data.get("weight", 0.5)
        rel = {
            "from_uid": uid_map[u],
            "to_uid": uid_map[v],
            "type": "SIMILAR_TO",
            "properties": {"similarity": round(weight, 3)},
        }
        relationships.append(rel)

    return {
        "query": query,
        "sources": sources,
        "nodes": nodes,
        "relationships": relationships
    }


def save_graph_to_json(graph_dict: Dict[str, Any], filename: str = "graph.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(graph_dict, f, indent=2, ensure_ascii=False)


def build_graph(
    papers: List[Dict[str, Any]],
    query: str,
    sources: List[str],
    model_name: str = "all-mpnet-base-v2",
    threshold: float = 0.4,
    visualize: bool = False
) -> Dict[str, Any]:
    G = build_similarity_graph(papers, model_name=model_name, threshold=threshold)
    result = create_graph_dict(G, papers, query, sources)
    if visualize:
        visualize_graph(G, papers)
    return result


