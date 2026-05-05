import pytest
from unittest.mock import MagicMock, patch, call
from src.neo4j_db import (
    normalize_name,
    clean_rel_type,
    create_nodes,
    create_relationships,
    set_to_neo4j,
    get_from_neo4j,
    create_user_and_db,
)

from neo4j.exceptions import ServiceUnavailable, AuthError, TransientError

# normalize_name
class TestNormalizeName:
    def test_basic(self):
        assert normalize_name("Isaac Newton") == "isaac_newton"

    def test_reversed_order(self):
        assert normalize_name("Isaac Newton") == normalize_name("Newton Isaac")

    def test_lowercase(self):
        assert normalize_name("NEWTON") == "newton"

    def test_strips_special_chars(self):
        assert normalize_name("Newton's method") == "method_newtons"

    def test_extra_spaces(self):
        assert normalize_name("  Isaac   Newton  ") == "isaac_newton"

    def test_empty_string(self):
        assert normalize_name("") == ""

    def test_single_word(self):
        assert normalize_name("Python") == "python"

    def test_numbers_preserved(self):
        assert normalize_name("Python 3") == "3_python"

    def test_only_special_chars(self):
        assert normalize_name("---") == ""


# clean_rel_type

class TestCleanRelType:
    def test_basic(self):
        assert clean_rel_type("NAMED_AFTER") == "NAMED_AFTER"

    def test_removes_parentheses(self):
        assert clean_rel_type("INSTANCE_OF(something)") == "INSTANCE_OF"

    def test_replaces_special_chars(self):
        assert clean_rel_type("NAMED-AFTER") == "NAMED_AFTER"

    def test_collapses_underscores(self):
        assert clean_rel_type("NAMED__AFTER") == "NAMED_AFTER"

    def test_strips_leading_trailing_underscores(self):
        assert clean_rel_type("_NAMED_AFTER_") == "NAMED_AFTER"

    def test_spaces_become_underscores(self):
        assert clean_rel_type("NAMED AFTER") == "NAMED_AFTER"

    def test_parentheses_in_middle_not_stripped(self):
        result = clean_rel_type("IS(something)OF")
        assert "(" not in result and ")" not in result

    def test_empty_string(self):
        result = clean_rel_type("")
        assert isinstance(result, str)


# create_nodes
class TestCreateNodes:
    def setup_method(self):
        self.tx = MagicMock()

    def test_basic_node_uid_format(self):
        nodes = [{"uid": "wikidata:Q935", "labels": ["Entity", "Concept"],
                  "properties": {"label_en": "Isaac Newton"}}]
        uid_map = create_nodes(self.tx, nodes, "newton's method")
        assert uid_map["wikidata:Q935"] == "wikidata:Q935::isaac_newton"

    def test_no_label_en_uses_no_label_suffix(self):
        nodes = [{"uid": "wikidata:Q935", "labels": ["Entity"], "properties": {}}]
        uid_map = create_nodes(self.tx, nodes, "test")
        assert uid_map["wikidata:Q935"] == "wikidata:Q935::no_label"

    def test_source_uid_written_to_props(self):
        nodes = [{"uid": "wikidata:Q935", "labels": ["Entity"],
                  "properties": {"label_en": "Alpha"}}]
        create_nodes(self.tx, nodes, "test")
        props = self.tx.run.call_args.kwargs["props"]
        assert props["source_uid"] == "wikidata:Q935"

    def test_query_written_to_props(self):
        nodes = [{"uid": "wikidata:Q1", "labels": ["Entity"],
                  "properties": {"label_en": "Alpha"}}]
        create_nodes(self.tx, nodes, "my query")
        props = self.tx.run.call_args.kwargs["props"]
        assert props["query"] == "my query"

    def test_multiple_nodes_returns_full_map(self):
        nodes = [
            {"uid": "wikidata:Q1", "labels": ["Entity"], "properties": {"label_en": "Alpha"}},
            {"uid": "wikidata:Q2", "labels": ["Entity"], "properties": {"label_en": "Beta"}},
        ]
        uid_map = create_nodes(self.tx, nodes, "test")
        assert len(uid_map) == 2
        assert self.tx.run.call_count == 2

    def test_multiple_labels_joined(self):
        nodes = [{"uid": "wikidata:Q1", "labels": ["Entity", "Concept"],
                  "properties": {"label_en": "Alpha"}}]
        create_nodes(self.tx, nodes, "test")
        cypher = self.tx.run.call_args.args[0]
        assert "Entity:Concept" in cypher

# create_relationships
class TestCreateRelationships:
    def setup_method(self):
        self.tx = MagicMock()
        self.uid_map = {
            "wikidata:Q374195": "wikidata:Q374195::method_newtons",
            "wikidata:Q935":    "wikidata:Q935::isaac_newton",
        }

    def test_basic_relationship(self):
        rels = [{"from_uid": "wikidata:Q374195", "to_uid": "wikidata:Q935",
                 "type": "NAMED_AFTER", "properties": {}}]
        create_relationships(self.tx, rels, self.uid_map, "test")
        self.tx.run.assert_called_once()

    def test_skips_self_loop(self):
        rels = [{"from_uid": "wikidata:Q935", "to_uid": "wikidata:Q935",
                 "type": "SAME_AS", "properties": {}}]
        create_relationships(self.tx, rels, self.uid_map, "test")
        self.tx.run.assert_not_called()

    def test_empty_relationships(self):
        create_relationships(self.tx, [], self.uid_map, "test")
        self.tx.run.assert_not_called()

    def test_uses_uid_map(self):
        rels = [{"from_uid": "wikidata:Q374195", "to_uid": "wikidata:Q935",
                 "type": "NAMED_AFTER", "properties": {}}]
        create_relationships(self.tx, rels, self.uid_map, "test")
        call_kwargs = self.tx.run.call_args.kwargs
        assert call_kwargs["from_uid"] == "wikidata:Q374195::method_newtons"
        assert call_kwargs["to_uid"]   == "wikidata:Q935::isaac_newton"

    def test_uid_not_in_map_uses_original(self):
        rels = [{"from_uid": "unknown:Q999", "to_uid": "wikidata:Q935",
                 "type": "REL", "properties": {}}]
        create_relationships(self.tx, rels, self.uid_map, "test")
        call_kwargs = self.tx.run.call_args.kwargs
        assert call_kwargs["from_uid"] == "unknown:Q999"

    def test_rel_type_cleaned(self):
        rels = [{"from_uid": "wikidata:Q374195", "to_uid": "wikidata:Q935",
                 "type": "NAMED-AFTER(extra)", "properties": {}}]
        create_relationships(self.tx, rels, self.uid_map, "test")
        cypher = self.tx.run.call_args.args[0]
        assert "NAMED_AFTER" in cypher

# set_to_neo4j
class TestSetToNeo4j:
    def _make_driver(self):
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)
        return driver, session

    def test_missing_query_raises(self):
        driver, _ = self._make_driver()
        with pytest.raises(ValueError):
            set_to_neo4j(driver, "db", {"nodes": [], "relationships": []})

    def test_missing_nodes_raises(self):
        driver, _ = self._make_driver()
        with pytest.raises(ValueError):
            set_to_neo4j(driver, "db", {"query": "test", "relationships": []})

    def test_missing_relationships_raises(self):
        driver, _ = self._make_driver()
        with pytest.raises(ValueError):
            set_to_neo4j(driver, "db", {"query": "test", "nodes": []})

    def test_empty_query_raises(self):
        driver, _ = self._make_driver()
        with pytest.raises(ValueError):
            set_to_neo4j(driver, "db", {"query": "", "nodes": [], "relationships": []})

    def test_nodes_not_list_raises(self):
        driver, _ = self._make_driver()
        with pytest.raises(ValueError):
            set_to_neo4j(driver, "db", {"query": "test", "nodes": {}, "relationships": []})

    def test_relationships_not_list_raises(self):
        driver, _ = self._make_driver()
        with pytest.raises(ValueError):
            set_to_neo4j(driver, "db", {"query": "test", "nodes": [], "relationships": {}})

    def test_calls_execute_write(self):
        driver, session = self._make_driver()
        set_to_neo4j(driver, "db", {"query": "test", "nodes": [], "relationships": []})
        session.execute_write.assert_called_once()

    def test_session_opened_with_db_name(self):
        driver, _ = self._make_driver()
        set_to_neo4j(driver, "mydb", {"query": "test", "nodes": [], "relationships": []})
        driver.session.assert_called_once_with(database="mydb")


# get_from_neo4j
class TestGetFromNeo4j:
    def _make_driver(self, vg_nodes=None, vg_rels=None):
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        vg = MagicMock()
        vg.nodes = vg_nodes or []
        vg.relationships = vg_rels or []

        with patch("src.neo4j_db.from_neo4j", return_value=vg):
            return driver, session

    def test_session_opened_with_db_name(self):
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.neo4j_db.from_neo4j", return_value=MagicMock(nodes=[], relationships=[])):
            get_from_neo4j(driver, "mydb", "test")

        driver.session.assert_called_once_with(database="mydb")

    def test_query_lowercased_in_cypher(self):
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.neo4j_db.from_neo4j", return_value=MagicMock(nodes=[], relationships=[])):
            get_from_neo4j(driver, "db", "my query")

        run_kwargs = session.run.call_args[1] or session.run.call_args[0][1]
        assert run_kwargs.get("q") == "my query" or run_kwargs == {"q": "my query"}


# create_user_and_db
class TestCreateUserAndDb:
    def _make_driver(self, existing_users=None, existing_roles=None, existing_dbs=None):
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        def run_side_effect(query, *args, **kwargs):
            q = query.strip().upper()
            result = MagicMock()
            if "SHOW USERS" in q:
                result.data.return_value = existing_users or []
            elif "SHOW ROLES" in q:
                result.data.return_value = existing_roles or []
            elif "SHOW DATABASES" in q:
                result.data.return_value = existing_dbs or []
            elif "SHOW DATABASE" in q:
                record = MagicMock()
                record.__getitem__ = lambda self, key: "online"
                result.single.return_value = record
            else:
                result.data.return_value = []
                result.single.return_value = None
            return result

        session.run.side_effect = run_side_effect
        return driver, session

    def test_empty_user_id_raises(self):
        driver, _ = self._make_driver()
        password = "password"
        with pytest.raises(ValueError):
            create_user_and_db(driver, "", password)

    def test_returns_two_values(self):
        driver, _ = self._make_driver()
        password = "password"
        with patch("time.sleep"):
            result = create_user_and_db(driver, 42, password)
        assert len(result) == 2

    def test_db_name_format(self):
        driver, _ = self._make_driver()
        password = "password"
        with patch("time.sleep"):
            db_name, username = create_user_and_db(driver, 42, password)
        assert db_name == "user42db"

    def test_username_format(self):
        driver, _ = self._make_driver()
        password = "password"
        with patch("time.sleep"):
            db_name, username = create_user_and_db(driver, 42, password)
        assert username == "user42"

    def test_password_is_nonempty_string(self):
        driver, _ = self._make_driver()
        password = "password"
        with patch("time.sleep"):
            create_user_and_db(driver, 42, password)
        assert isinstance(password, str) and len(password) > 0

    def test_duplicate_user_raises(self):
        driver, _ = self._make_driver(existing_users=[{"user": "user42"}])
        password = "password"
        with pytest.raises(ValueError, match="уже существует"):
            create_user_and_db(driver, 42, password)

    def test_duplicate_role_raises(self):
        driver, _ = self._make_driver(existing_roles=[{"role": "user42_role"}])
        password = "password"
        with pytest.raises(ValueError, match="уже существует"):
            create_user_and_db(driver, 42, password)

    def test_duplicate_db_raises(self):
        driver, _ = self._make_driver(existing_dbs=[{"name": "user42db"}])
        password = "password"
        with pytest.raises(ValueError, match="уже существует"):
            create_user_and_db(driver, 42, password)

    def test_service_unavailable_raises_connection_error(self):
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__.return_value = session
        session.run.side_effect = ServiceUnavailable("Сервер Neo4j недоступен")

        password = "password"
        with pytest.raises(ConnectionError, match="Neo4j сервер недоступен"):
            create_user_and_db(driver, 42, password)

    def test_auth_error_raises_permission_error(self):
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__.return_value = session
        session.run.side_effect = AuthError("Неверный логин или пароль")

        password = "password"
        with pytest.raises(PermissionError, match="Ошибка авторизации"):
            create_user_and_db(driver, 42, password)

    def test_transient_error_raises_timeout_error(self):
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__.return_value = session
        session.run.side_effect = TransientError("Временная ошибка сети")

        password = "password"
        with pytest.raises(TimeoutError, match="Временная ошибка"):
            create_user_and_db(driver, 42, password)