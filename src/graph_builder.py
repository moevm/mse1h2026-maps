import json

import matplotlib.pyplot as plt
import networkx as nx
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


def load_papers(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        papers = json.load(f)
    return papers


def preprocess_text(text):
    if text is None or text.strip() == "":
        return ""

    # I'll write it someday...

    return text.strip()


# The algorithm is based on embedding.
# Smart neural networks turn article descriptions into vectors.
# And the proximity of the articles is compared using a cosine measure.


# Experimentally, I found such models:
# all-mpnet-base-v2 (cool, but slow)
# all-MiniLM-L6-v2 (tolerable and fast)
# allenai-specter (best, very slow)


def build_similarity_graph(papers, model_name="all-mpnet-base-v2", threshold=0.5):

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


def visualize_graph(G, papers, figsize=(12, 8)):
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


def export_to_custom_json(G, papers, filename="graph_custom.json"):

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

        properties = {
            "label_en": title,
        }
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

        node = {"uid": uid, "labels": ["Entity", "Paper"], "properties": properties}
        nodes.append(node)

    for u, v, data in G.edges(data=True):
        weight = data.get("weight", 0.5)
        rel = {
            "from_uid": uid_map[u],
            "to_uid": uid_map[v],
            "type": "SIMILAR_TO",
            "properties": {"similarity": round(weight, 3)},
        }
        relationships.append(rel)

    output = {"nodes": nodes, "relationships": relationships}

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def build_graph(json_file):
    papers = load_papers(json_file)

    G = build_similarity_graph(papers, threshold=0.3)

    export_to_custom_json(G, papers, "graph.json")

    visualize_graph(G, papers)