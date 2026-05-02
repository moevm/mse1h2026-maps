# unit_tests.py

import pytest
from unittest.mock import patch, Mock
import requests
from typing import Dict, Any

# Импортируем тестируемые функции
from wikidata import (
    get_entity_id_by_label,
    collect_ids,
    fetch_labels_map,
    enrich_structure,
    transform_to_neo4j_format,
    fetch_wikidata
)
from wikipedia import get_links_descriptions, fetch_wikipedia
from github import fetch_github
from open_alex import decode_inverted_abstract, fetch_open_alex


# ==================== Фикстуры ====================

@pytest.fixture
def sample_wikidata_response():
    """Пример ответа Wikidata"""
    return {
        "entities": {
            "Q190291": {
                "id": "Q190291",
                "labels": {"en": {"value": "Newton's method"}},
                "descriptions": {"en": {"value": "Root-finding algorithm"}},
                "claims": {
                    "P138": [{
                        "mainsnak": {
                            "property": "P138",
                            "property_label": "named after",
                            "property_description": "name of a significant person or entity",
                            "datavalue": {
                                "type": "wikibase-entityid",
                                "value": {
                                    "id": "Q9433",
                                    "label": "Isaac Newton",
                                    "descriptions": "English physicist and mathematician"
                                }
                            }
                        }
                    }]
                }
            }
        }
    }


@pytest.fixture
def sample_github_response():
    """Пример ответа GitHub API"""
    return {
        "items": [
            {
                "html_url": "https://github.com/test/repo",
                "description": "Test repository",
                "topics": ["python", "test"],
                "language": "Python"
            }
        ]
    }


@pytest.fixture
def sample_openalex_response():
    """Пример ответа OpenAlex API"""
    return {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "title": "Test Paper",
                "abstract_inverted_index": {
                    "test": [0],
                    "paper": [1]
                }
            }
        ]
    }


@pytest.fixture
def sample_wikipedia_response():
    """Пример ответа Wikipedia API"""
    return {
        "query": {
            "pages": {
                "12345": {
                    "pageid": 12345,
                    "title": "Test Article",
                    "extract": "This is a test article content.",
                    "links": [
                        {"ns": 0, "title": "Link1"},
                        {"ns": 0, "title": "Link2"}
                    ]
                }
            }
        }
    }


# ==================== Тесты для Wikipedia ====================

class TestWikipedia:
    """Тесты для Wikipedia парсера"""
    
    @patch('wikipedia.requests.get')
    def test_fetch_wikipedia_success(self, mock_get, sample_wikipedia_response):
        """Тест успешного получения статьи Wikipedia"""
        # Мокаем первый запрос (основная статья)
        mock_response1 = Mock()
        mock_response1.json.return_value = sample_wikipedia_response
        
        # Мокаем второй запрос (описания ссылок)
        mock_response2 = Mock()
        mock_response2.json.return_value = {
            "query": {
                "pages": {
                    "1": {"title": "Link1", "extract": "Description 1"},
                    "2": {"title": "Link2", "extract": "Description 2"}
                }
            }
        }
        
        # Настраиваем последовательные возвраты
        mock_get.side_effect = [mock_response1, mock_response2]
        
        result = fetch_wikipedia("Test Article")
        
        assert result is not None
        assert "query" in result
        assert "pages" in result["query"]
        
        # Проверяем, что было два вызова
        assert mock_get.call_count == 2
    
    @patch('wikipedia.requests.get')
    def test_fetch_wikipedia_not_found(self, mock_get):
        """Тест: статья не найдена"""
        mock_response = Mock()
        mock_response.json.return_value = {"query": {"pages": {"-1": {}}}}
        mock_get.return_value = mock_response
        
        result = fetch_wikipedia("Nonexistent Article")
        
        assert isinstance(result, dict)
    
    @patch('wikipedia.requests.get')
    def test_fetch_wikipedia_exception(self, mock_get):
        """Тест: ошибка сети"""
        mock_get.side_effect = Exception("Network error")
        
        result = fetch_wikipedia("Test")
        
        assert result == {}
    
    def test_get_links_descriptions_empty(self):
        """Тест: пустой список ссылок"""
        result = get_links_descriptions([])
        assert result == {}
    
    @patch('wikipedia.requests.get')
    def test_get_links_descriptions_batch(self, mock_get):
        """Тест: получение описаний для нескольких ссылок"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "query": {
                "pages": {
                    "1": {"title": "Link1", "extract": "Description 1"},
                    "2": {"title": "Link2", "extract": "Description 2"}
                }
            }
        }
        mock_get.return_value = mock_response
        
        result = get_links_descriptions(["Link1", "Link2"])
        
        assert isinstance(result, dict)
        assert len(result) > 0


# ==================== Тесты для GitHub ====================

class TestGitHub:
    """Тесты для GitHub парсера"""
    
    @patch('github.requests.get')
    def test_fetch_github_success(self, mock_get, sample_github_response):
        """Тест успешного поиска репозиториев"""
        mock_response = Mock()
        mock_response.json.return_value = sample_github_response
        mock_get.return_value = mock_response
        
        result = fetch_github("test")
        
        assert isinstance(result, list)
        assert len(result) > 0
        assert result[0]["url"] == "https://github.com/test/repo"
        assert result[0]["description"] == "Test repository"
    
    @patch('github.requests.get')
    def test_fetch_github_no_results(self, mock_get):
        """Тест: результаты не найдены"""
        mock_response = Mock()
        mock_response.json.return_value = {"items": []}
        mock_get.return_value = mock_response
        
        result = fetch_github("nonexistent_topic_xyz")
        
        assert result == []
    
    @patch('github.requests.get')
    def test_fetch_github_exception(self, mock_get):
        """Тест: ошибка API"""
        mock_get.side_effect = Exception("API Error")
        
        result = fetch_github("test")
        
        assert result == {}
    
    @patch('github.requests.get')
    def test_fetch_github_uses_topic_search(self, mock_get):
        """Тест: проверка параметров запроса"""
        mock_response = Mock()
        mock_response.json.return_value = {"items": []}
        mock_get.return_value = mock_response
        
        result = fetch_github("test_topic")
        
        # Проверяем, что был вызван с правильными параметрами
        call_args = mock_get.call_args
        assert call_args is not None
        params = call_args[1].get("params", {})
        assert "topic:test_topic" in params["q"]


# ==================== Тесты для OpenAlex ====================

class TestOpenAlex:
    """Тесты для OpenAlex парсера"""
    
    def test_decode_inverted_abstract_normal(self):
        """Тест: нормальный инвертированный индекс"""
        inverted = {
            "hello": [0],
            "world": [1]
        }
        result = decode_inverted_abstract(inverted)
        assert result == "hello world"
    
    def test_decode_inverted_abstract_with_gaps(self):
        """Тест: с пропусками в позициях"""
        inverted = {
            "hello": [0],
            "world": [2]
        }
        result = decode_inverted_abstract(inverted)
        assert result == "hello  world"
    
    def test_decode_inverted_abstract_multiple_positions(self):
        """Тест: слово на нескольких позициях"""
        inverted = {
            "test": [0, 2],
            "word": [1]
        }
        result = decode_inverted_abstract(inverted)
        assert result == "test word test"
    
    def test_decode_inverted_abstract_empty(self):
        """Тест: пустой индекс"""
        result = decode_inverted_abstract({})
        assert result == ""
    
    def test_decode_inverted_abstract_none(self):
        """Тест: None вместо словаря"""
        result = decode_inverted_abstract(None)
        assert result == ""
    
    @patch('open_alex.requests.get')
    def test_fetch_open_alex_success(self, mock_get, sample_openalex_response):
        """Тест успешного получения данных OpenAlex"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_openalex_response
        mock_get.return_value = mock_response
        
        result = fetch_open_alex("test")
        
        assert result is not None
        assert "results" in result
    
    @patch('open_alex.requests.get')
    def test_fetch_open_alex_http_error(self, mock_get):
        """Тест: HTTP ошибка"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        result = fetch_open_alex("test")
        
        assert result == []
    
    @patch('open_alex.requests.get')
    def test_fetch_open_alex_exception(self, mock_get):
        """Тест: исключение при запросе"""
        mock_get.side_effect = Exception("Connection error")
        
        result = fetch_open_alex("test")
        
        assert result == []


# ==================== Тесты для Wikidata ====================

class TestWikidata:
    """Тесты для Wikidata парсера"""
    
    @patch('wikidata.requests.get')
    def test_get_entity_id_by_label_success(self, mock_get):
        """Тест: поиск QID по названию"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "search": [{"id": "Q123"}]
        }
        mock_get.return_value = mock_response
        
        result = get_entity_id_by_label("Test")
        
        assert result == "Q123"
    
    @patch('wikidata.requests.get')
    def test_get_entity_id_by_label_not_found(self, mock_get):
        """Тест: QID не найден"""
        mock_response = Mock()
        mock_response.json.return_value = {"search": []}
        mock_get.return_value = mock_response
        
        result = get_entity_id_by_label("Nonexistent")
        
        assert result is None
    
    def test_collect_ids_from_dict(self):
        """Тест: сбор ID из словаря"""
        data = {
            "entity-type": "item",
            "id": "Q123",
            "property": "P456"
        }
        result = collect_ids(data)
        assert "Q123" in result
        assert "P456" in result
    
    def test_collect_ids_from_list(self):
        """Тест: сбор ID из списка"""
        data = [
            {"entity-type": "item", "id": "Q123"},
            {"property": "P456"}
        ]
        result = collect_ids(data)
        assert "Q123" in result
        assert "P456" in result
    
    def test_collect_ids_from_string(self):
        """Тест: сбор ID из строки"""
        data = "Q123"
        result = collect_ids(data)
        assert "Q123" in result
    
    def test_collect_ids_invalid_string(self):
        """Тест: игнорирование не-ID строк"""
        data = "not an id"
        result = collect_ids(data)
        assert result == set()
    
    def test_collect_ids_nested(self):
        """Тест: сбор ID из вложенных структур"""
        data = {
            "level1": {
                "level2": {
                    "entity-type": "item",
                    "id": "Q789"
                }
            }
        }
        result = collect_ids(data)
        assert "Q789" in result
    
    @patch('wikidata.requests.get')
    def test_fetch_labels_map(self, mock_get):
        """Тест: загрузка меток для ID"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "entities": {
                "Q123": {
                    "labels": {"en": {"value": "Test Label"}},
                    "descriptions": {"en": {"value": "Test Description"}}
                }
            }
        }
        mock_get.return_value = mock_response
        
        result = fetch_labels_map({"Q123"})
        
        assert "Q123" in result
        assert result["Q123"][0] == "Test Label"
        assert result["Q123"][1] == "Test Description"
    
    def test_enrich_structure_entity(self):
        """Тест: обогащение сущности"""
        data = {"entity-type": "item", "id": "Q123"}
        labels = {"Q123": ["Test Label", "Test Description"]}
        
        result = enrich_structure(data, labels)
        
        assert result["id"] == "Q123"
        assert result["label"] == "Test Label"
        assert result["descriptions"] == "Test Description"
    
    def test_enrich_structure_property(self):
        """Тест: обогащение свойства"""
        data = {"property": "P123"}
        labels = {"P123": ["Test Prop", "Prop Description"]}
        
        result = enrich_structure(data, labels)
        
        assert result["property_label"] == "Test Prop"
        assert result["property_descriptions"] == "Prop Description"
    
    def test_enrich_structure_list(self):
        """Тест: обогащение списка"""
        data = [
            {"entity-type": "item", "id": "Q123"},
            {"entity-type": "item", "id": "Q456"}
        ]
        labels = {
            "Q123": ["Label1", "Desc1"],
            "Q456": ["Label2", "Desc2"]
        }
        
        result = enrich_structure(data, labels)
        
        assert len(result) == 2
        assert result[0]["label"] == "Label1"
        assert result[1]["label"] == "Label2"
    
    @patch('wikidata.get_entity_id_by_label')
    @patch('wikidata.requests.get')
    @patch('wikidata.fetch_labels_map')
    def test_fetch_wikidata_integration(self, mock_fetch_labels, mock_get, mock_get_id, sample_wikidata_response):
        """Тест: интеграция fetch_wikidata"""
        mock_get_id.return_value = "Q190291"
        
        mock_response = Mock()
        mock_response.json.return_value = sample_wikidata_response
        mock_get.return_value = mock_response
        
        mock_fetch_labels.return_value = {
            "Q190291": ["Newton's method", "Root-finding algorithm"],
            "Q9433": ["Isaac Newton", "English physicist and mathematician"]
        }
        
        result = fetch_wikidata("Newton's method")
        
        assert result is not None
        assert "query" in result
        assert "nodes" in result


# ==================== Запуск тестов ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])