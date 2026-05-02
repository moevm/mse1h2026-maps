import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import unittest
from unittest.mock import MagicMock, patch

import networkx as nx
import numpy as np

from src.graph_builder import (
    FORMAT_REGISTRY,
    _github_collect_nodes,
    _github_matches,
    _openalex_collect_nodes,
    _wikidata_collect_nodes,
    _wikipedia_collect_nodes,
    _wikipedia_matches,
    add_explicit_relationships,
    build_graph_from_any,
    build_similarity_graph_from_nodes,
    detect_format,
    graph_to_output_dict,
    parse_any,
    restore_abstract_from_inverted_index,
)


class TestFormatOpenAlex(unittest.TestCase):
    def test_missing_results_and_meta(self):
        bad_data = {"something": "else"}
        with self.assertRaises(ValueError) as ctx:
            _openalex_collect_nodes(bad_data)
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_results_not_list(self):
        bad_data = {"results": "not_a_list", "meta": {}}
        with self.assertRaises(ValueError) as ctx:
            _openalex_collect_nodes(bad_data)
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_invalid_paper_not_dict(self):
        bad_data = {"results": ["string_instead_of_dict"], "meta": {}}
        with self.assertRaises(ValueError) as ctx:
            _openalex_collect_nodes(bad_data)
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_valid_openalex_data(self):
        data = {
            "results": [
                {"id": "W123", "title": "Test Paper", "abstract": "An abstract"}
            ],
            "meta": {},
        }
        nodes = _openalex_collect_nodes(data)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["uid"], "openalex:W123")


class TestFormatWikidata(unittest.TestCase):
    def test_not_dict(self):
        with self.assertRaises(ValueError) as ctx:
            _wikidata_collect_nodes(["not", "a", "dict"])
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_missing_nodes_or_relationships(self):
        bad = {"nodes": []}
        with self.assertRaises(ValueError) as ctx:
            _wikidata_collect_nodes(bad)
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

        bad2 = {"relationships": []}
        with self.assertRaises(ValueError):
            _wikidata_collect_nodes(bad2)

    def test_nodes_not_list(self):
        bad = {"nodes": "not_a_list", "relationships": []}
        with self.assertRaises(ValueError) as ctx:
            _wikidata_collect_nodes(bad)
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_relationships_not_list(self):
        bad = {"nodes": [], "relationships": "not_a_list"}
        with self.assertRaises(ValueError) as ctx:
            _wikidata_collect_nodes(bad)
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_valid_wikidata(self):
        data = {
            "nodes": [{"uid": "Q1", "properties": {"label_en": "Test"}}],
            "relationships": [],
        }
        nodes = _wikidata_collect_nodes(data)
        self.assertEqual(len(nodes), 1)


class TestFormatGitHub(unittest.TestCase):
    def test_matches_function(self):
        valid = [
            {"url": "https://example.com", "description": "desc", "topics": ["topic"]}
        ]
        self.assertTrue(_github_matches(valid))
        invalid = {"not": "list"}
        self.assertFalse(_github_matches(invalid))
        invalid2 = [{"url": "x"}]
        self.assertFalse(_github_matches(invalid2))

    def test_not_list(self):
        with self.assertRaises(ValueError) as ctx:
            _github_collect_nodes({"some": "dict"})
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_empty_list(self):
        with self.assertRaises(ValueError) as ctx:
            _github_collect_nodes([])
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_element_not_dict(self):
        bad = ["string"]
        with self.assertRaises(ValueError) as ctx:
            _github_collect_nodes(bad)
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_missing_required_keys(self):
        bad = [{"url": "x", "description": "y"}]
        with self.assertRaises(ValueError) as ctx:
            _github_collect_nodes(bad)
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_valid_github(self):
        data = [{"url": "https://x.com", "description": "test", "topics": ["a"]}]
        nodes = _github_collect_nodes(data)
        self.assertEqual(len(nodes), 1)
        self.assertTrue(nodes[0]["uid"].startswith("github:"))


class TestFormatWikipedia(unittest.TestCase):
    def test_matches(self):
        valid = {"query": {"pages": {"123": {"title": "Test"}}}}
        self.assertTrue(_wikipedia_matches(valid))
        invalid = {"no_query": {}}
        self.assertFalse(_wikipedia_matches(invalid))
        invalid2 = {"query": "not dict"}
        self.assertFalse(_wikipedia_matches(invalid2))

    def test_not_dict(self):
        with self.assertRaises(ValueError) as ctx:
            _wikipedia_collect_nodes(["not", "dict"])
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_missing_query(self):
        with self.assertRaises(ValueError) as ctx:
            _wikipedia_collect_nodes({"some": "thing"})
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_query_not_dict(self):
        bad = {"query": "string"}
        with self.assertRaises(ValueError) as ctx:
            _wikipedia_collect_nodes(bad)
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_missing_pages(self):
        bad = {"query": {}}
        with self.assertRaises(ValueError) as ctx:
            _wikipedia_collect_nodes(bad)
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_pages_not_dict(self):
        bad = {"query": {"pages": []}}
        with self.assertRaises(ValueError) as ctx:
            _wikipedia_collect_nodes(bad)
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_pages_empty(self):
        bad = {"query": {"pages": {}}}
        with self.assertRaises(ValueError) as ctx:
            _wikipedia_collect_nodes(bad)
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_page_not_dict(self):
        bad = {"query": {"pages": {"1": "not_a_dict"}}}
        with self.assertRaises(ValueError) as ctx:
            _wikipedia_collect_nodes(bad)
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_valid_wikipedia(self):
        data = {
            "query": {
                "pages": {
                    "123": {"pageid": 123, "title": "Test", "extract": "extract text"}
                }
            }
        }
        nodes = _wikipedia_collect_nodes(data)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["uid"], "wikipedia:123")


class TestGraphBuildingErrors(unittest.TestCase):

    @patch("sentence_transformers.SentenceTransformer")
    def test_build_similarity_graph_empty_nodes(self, mock_model):
        with self.assertRaises(ValueError) as ctx:
            build_similarity_graph_from_nodes([])
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_build_similarity_graph_bad_threshold(self):
        node = [{"uid": "1", "text": "text", "original": {}, "source_type": "test"}]
        with self.assertRaises(ValueError) as ctx:
            build_similarity_graph_from_nodes(node, threshold=-0.1)
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

        with self.assertRaises(ValueError) as ctx:
            build_similarity_graph_from_nodes(node, threshold=1.5)
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    @patch("sentence_transformers.SentenceTransformer")
    def test_valid_graph_building(self, mock_model):
        instance = mock_model.return_value
        instance.encode.return_value = np.array([[0.5, 0.5], [0.5, 0.5]])
        nodes = [
            {"uid": "n1", "text": "hello", "original": {}, "source_type": "test"},
            {"uid": "n2", "text": "world", "original": {}, "source_type": "test"},
        ]
        G = build_similarity_graph_from_nodes(nodes)
        self.assertEqual(len(G.nodes), 2)

    def test_add_explicit_relationships_bad_input(self):
        G = nx.Graph()
        G.add_node(0, uid="u1")
        with self.assertRaises(ValueError) as ctx:
            add_explicit_relationships(G, "not_a_list")
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_build_graph_from_any_unknown_format(self):
        result = build_graph_from_any({"some": "unknown"}, query="test")
        self.assertEqual(result["nodes"], [])
        self.assertEqual(result["sources"], [])

    @patch("src.graph_builder.parse_any")
    def test_build_graph_from_any_parse_error(self, mock_parse):
        mock_parse.side_effect = ValueError("GraphBuilder: parse failed")
        with self.assertRaises(ValueError) as ctx:
            build_graph_from_any({"any": "data"}, query="test")
        self.assertTrue(str(ctx.exception).startswith("GraphBuilder:"))

    def test_build_graph_from_any_smoke(self):
        oa = {"results": [{"id": "W123", "title": "Title"}], "meta": {}}
        wiki = {"query": {"pages": {"1": {"title": "Page", "extract": "extract"}}}}
        github = [{"url": "https://x.com", "description": "desc", "topics": []}]
        result = build_graph_from_any([oa, wiki, github], query="test", threshold=0.9)
        self.assertIn("query", result)
        self.assertIn("nodes", result)
        self.assertIn("relationships", result)
        self.assertTrue(len(result["nodes"]) > 0)


if __name__ == "__main__":
    unittest.main()
