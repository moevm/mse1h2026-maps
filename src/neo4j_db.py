import logging
import re
import time

from neo4j.exceptions import (
    AuthError,
    ServiceUnavailable,
    SessionExpired,
    TransientError,
)
from neo4j_viz.neo4j import from_neo4j

logger = logging.getLogger(__name__)


def normalize_name(name):
    words = name.lower().strip().split()
    words = sorted(words)
    words = [re.sub(r"[^a-z0-9]", "", w) for w in words]
    return "_".join(words)


def clean_rel_type(rel_type):
    rel_type = re.sub(r"\([^)]*\)$", "", rel_type)
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", rel_type)
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip("_")
    return cleaned


def wait_for_db_online(session, db_name, timeout=30, interval=1):
    start = time.time()
    while True:
        result = session.run(
            f"SHOW DATABASE {db_name} YIELD name, currentStatus "
            f"WHERE name = '{db_name}' RETURN currentStatus"
        )
        record = result.single()

        if record and record["currentStatus"] == "online":
            return True

        if time.time() - start > timeout:
            raise TimeoutError(f"База {db_name} не перешла в ONLINE за {timeout} сек")

        time.sleep(interval)


def create_user_and_db(driver, user_id, neo4j_password):
    if not user_id:
        raise ValueError("user_id не может быть пустым")

    if not neo4j_password:
        raise ValueError("neo4j_password не может быть пустым")

    neo4j_username = f"user{user_id}"
    db_name = f"{neo4j_username}db"
    role_name = f"{neo4j_username}_role"

    user_created = False
    role_created = False
    db_created = False

    try:
        with driver.session() as session:
            existing_users = session.run("SHOW USERS").data()
            if neo4j_username in [u["user"] for u in existing_users]:
                raise ValueError(f"Пользователь {neo4j_username} уже существует")

            session.run(
                f"CREATE USER {neo4j_username} "
                "SET PASSWORD $password CHANGE NOT REQUIRED",
                password=neo4j_password,
            )
            user_created = True

            existing_roles = session.run("SHOW ROLES").data()
            if role_name in [r["role"] for r in existing_roles]:
                raise ValueError(f"Роль {role_name} уже существует")

            session.run(f"CREATE ROLE {role_name}")
            role_created = True

            existing_dbs = session.run("SHOW DATABASES").data()
            if db_name in [d["name"] for d in existing_dbs]:
                raise ValueError(f"База {db_name} уже существует")

            session.run(f"CREATE DATABASE {db_name}")
            db_created = True

            wait_for_db_online(session, db_name)

            session.run(f"GRANT ROLE {role_name} TO {neo4j_username}")
            session.run(f"GRANT ACCESS ON DATABASE {db_name} TO {role_name}")
            session.run(f"GRANT READ {{*}} ON GRAPH {db_name} TO {role_name}")
            session.run(f"GRANT TRAVERSE ON GRAPH {db_name} TO {role_name}")
            session.run(f"GRANT WRITE ON GRAPH {db_name} TO {role_name}")
            session.run(
                f"GRANT CREATE NEW NODE LABEL ON DATABASE {db_name} TO {role_name}"
            )
            session.run(
                f"GRANT CREATE NEW RELATIONSHIP TYPE ON DATABASE {db_name} TO {role_name}"
            )
            session.run(
                f"GRANT CREATE NEW PROPERTY NAME ON DATABASE {db_name} TO {role_name}"
            )

    except ServiceUnavailable as e:
        raise ConnectionError(f"Neo4j сервер недоступен: {e}") from e

    except AuthError as e:
        raise PermissionError(f"Ошибка авторизации: {e}") from e

    except TransientError as e:
        raise TimeoutError(f"Временная ошибка, попробуйте позже: {e}") from e

    except ValueError:
        raise

    except Exception as e:
        try:
            with driver.session() as session:
                if db_created:
                    session.run(f"DROP DATABASE {db_name} IF EXISTS")
                if role_created:
                    session.run(f"DROP ROLE {role_name} IF EXISTS")
                if user_created:
                    session.run(f"DROP USER {neo4j_username} IF EXISTS")
        except Exception as rollback_error:
            logger.error(f"Ошибка отката: {rollback_error}")
        raise RuntimeError(f"Не удалось создать пользователя: {e}") from e

    return db_name, neo4j_username


def create_nodes(tx, nodes, query):

    uid_map = {}
    current_time = time.time()

    for node in nodes:
        try:

            labels = ":".join(node["labels"])
            props = node.get("properties", {})
            old_uid = node["uid"]

            label_en = props.get("label_en") or ""
            label_ru = props.get("label_ru") or ""

            if label_en:
                semantic_part = normalize_name(label_en)
            elif label_ru:
                semantic_part = normalize_name(label_ru)
            else:
                for key, value in props.items():
                    if key.startswith("label_") and value:
                        semantic_part = normalize_name(str(value))
                        break
                else:
                    semantic_part = "no_label"

            if "descriptions" in node:
                props["descriptions"] = node["descriptions"]

            props["source_uid"] = old_uid
            props["query"] = query
            props["created_at"] = current_time
            new_uid = f"{old_uid}::{semantic_part}"
            uid_map[old_uid] = new_uid
            tx.run(
                f"MERGE (n:{labels} {{uid: $uid, query: $query_param}}) SET n += $props",
                uid=new_uid,
                query_param=query,
                props=props,
            )

        except ServiceUnavailable as e:
            raise ConnectionError(
                f"Neo4j сервер недоступен при создании узла {node.get('uid', '?')}: {e}"
            ) from e
        except AuthError as e:
            raise PermissionError(
                f"Ошибка авторизации при создании узла {node.get('uid', '?')}: {e}"
            ) from e
        except ValueError:
            raise

    return uid_map


def create_relationships(tx, relationships, uid_map, query):
    for rel in relationships:
        from_uid = uid_map.get(rel["from_uid"], rel["from_uid"])
        to_uid = uid_map.get(rel["to_uid"], rel["to_uid"])

        if from_uid == to_uid:
            continue

        props = rel.get("properties", {}).copy()
        if rel.get("descriptions"):
            props["descriptions"] = rel["descriptions"]

        clean_type = clean_rel_type(rel["type"])

        try:
            tx.run(
                f"""
                MATCH (a {{uid: $from_uid, query: $query_param}})
                MATCH (b {{uid: $to_uid, query: $query_param}})
                MERGE (a)-[r:{clean_type}]->(b)
                SET r += $props
                """,
                from_uid=from_uid,
                to_uid=to_uid,
                query_param=query,
                props=props,
            )
        except ServiceUnavailable as e:
            raise ConnectionError(
                f"Neo4j сервер недоступен при создании связи: {e}"
            ) from e
        except AuthError as e:
            raise PermissionError(f"Ошибка авторизации при создании связи: {e}") from e
        except TransientError as e:
            raise TimeoutError(
                f"Временная ошибка Neo4j при создании связи, попробуйте позже: {e}"
            ) from e


def set_to_neo4j(driver, db_name, data):

    if "query" not in data:
        raise ValueError("data должна содержать поле query")
    if "nodes" not in data or "relationships" not in data:
        raise ValueError("data должна содержать поля nodes и relationships")
    if not data["query"]:
        raise ValueError("query не может быть пустым")
    if not isinstance(data["nodes"], list):
        raise ValueError("nodes должен быть списком")
    if not isinstance(data["relationships"], list):
        raise ValueError("relationships должен быть списком")

    for i, node in enumerate(data["nodes"]):
        if "uid" not in node:
            raise ValueError(f"Узел {i} не содержит обязательное поле uid")
        if "labels" not in node or not node["labels"]:
            raise ValueError(
                f"Узел {i} не содержит обязательное поле labels или оно пустое"
            )
        if not isinstance(node["labels"], list):
            raise ValueError(f"labels узла {i} должен быть списком")
        if "properties" in node and not isinstance(node["properties"], dict):
            raise ValueError(f"properties узла {i} должен быть словарём")

    uids_in_nodes = {node["uid"] for node in data["nodes"]}

    for i, rel in enumerate(data["relationships"]):
        if "properties" in rel and not isinstance(rel["properties"], dict):
            raise ValueError(f"properties связи {i} должен быть словарём")
        if "from_uid" not in rel:
            raise ValueError(f"Связь {i} не содержит поле from_uid")
        if "to_uid" not in rel:
            raise ValueError(f"Связь {i} не содержит поле to_uid")
        if "type" not in rel:
            raise ValueError(f"Связь {i} не содержит поле type")
        if not isinstance(rel["type"], str) or not rel["type"].strip():
            raise ValueError(f"type связи {i} не может быть пустым")

        if rel["from_uid"] not in uids_in_nodes:
            raise ValueError(
                f"Связь {i}: from_uid '{rel['from_uid']}' не найден среди узлов. "
            )
        if rel["to_uid"] not in uids_in_nodes:
            raise ValueError(
                f"Связь {i}: to_uid '{rel['to_uid']}' не найден среди узлов. "
                f"Доступные uid: {sorted(uids_in_nodes)[:10]}"
            )

    query = data["query"].strip().lower()

    def _execute(tx, data):
        uid_map = create_nodes(tx, data["nodes"], query)
        create_relationships(tx, data["relationships"], uid_map, query)

    try:
        with driver.session(database=db_name) as session:
            session.execute_write(_execute, data)
    except (ServiceUnavailable, SessionExpired, TransientError) as e:
        raise ConnectionError(
            f"Neo4j не доступен при записи графа '{query}': {e}"
        ) from e
    except AuthError as e:
        raise PermissionError(
            f"Ошибка авторизации при записи графа '{query}': {e}"
        ) from e
    except (ValueError, ConnectionError, PermissionError, TimeoutError) as e:
        raise
    except Exception as e:
        raise RuntimeError(f"Ошибка при записи графа '{query}': {e}") from e


def get_from_neo4j(driver, db_name, query):

    try:
        with driver.session(database=db_name) as session:
            result = session.run(
                """
                MATCH (n)
                WHERE n.query = $q
                OPTIONAL MATCH (n)-[r]->(m)
                WHERE m.query = $q
                RETURN n, r, m
                """,
                {"q": query},
            )

            VG = from_neo4j(result, row_limit=10000)

            nodes = []
            for node in VG.nodes:
                nodes.append(
                    {
                        "id": node.id,
                        "caption": node.caption,
                        "labels": node.properties.get("labels", []),
                        "properties": node.properties,
                    }
                )

            relationships = []
            for rel in VG.relationships:
                relationships.append(
                    {
                        "id": rel.id,
                        "from": rel.source,
                        "to": rel.target,
                        "caption": rel.properties.get("type", ""),
                        "properties": rel.properties,
                    }
                )

            return {"nodes": nodes, "relationships": relationships}

    except ServiceUnavailable as e:
        raise ConnectionError(f"Neo4j не доступен: {e}") from e

    except AuthError as e:
        raise PermissionError(f"Ошибка авторизации: {e}") from e

    except AttributeError as e:
        raise ValueError(f"Отсутствует поле в данных: {e}") from e

    except Exception as e:
        raise RuntimeError(f"Ошибка: {e}") from e


def add_node(driver, db_name, query, nodes=None, relationships=None):

    result = {}

    def _execute(tx):
        uid_map = {}
        if nodes:
            uid_map = create_nodes(tx, nodes, query)
            result.update(uid_map)

        if relationships:
            create_relationships(tx, relationships, uid_map, query)

    try:
        with driver.session(database=db_name) as session:
            session.execute_write(_execute)
            return result

    except (ServiceUnavailable, SessionExpired, TransientError) as e:
        raise ConnectionError(f"Neo4j не доступен: {e}") from e
    except AuthError as e:
        raise PermissionError(f"Ошибка авторизации: {e}") from e
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Ошибка при создании элементов графа: {e}") from e


def delete_node(driver, db_name, query, uid):

    def _execute(tx):
        result = tx.run(
            "MATCH (n {uid: $uid, query: $q}) RETURN count(n) AS cnt",
            uid=uid,
            q=query,
        )
        record = result.single()
        if not record or record["cnt"] == 0:
            raise ValueError(f"Узел с uid='{uid}' не найден в графе '{query}'")
        tx.run(
            "MATCH (n {uid: $uid, query: $q}) DETACH DELETE n",
            uid=uid,
            q=query,
        )

    try:
        with driver.session(database=db_name) as session:
            session.execute_write(_execute)
    except (ServiceUnavailable, SessionExpired, TransientError) as e:
        raise ConnectionError(f"Neo4j не доступен при удалении узла: {e}") from e
    except AuthError as e:
        raise PermissionError(f"Ошибка авторизации при удалении узла: {e}") from e
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Ошибка при удалении узла '{uid}': {e}") from e


def get_history(driver, user_id):
    db_name = f"user{user_id}db"

    def db_exists():
        try:
            with driver.session() as session:
                result = session.run("SHOW DATABASES")
                dbs = [record["name"] for record in result]
                return db_name in dbs
        except Exception:
            return False

    if not db_exists():
        return {"history": []}

    try:
        with driver.session(database=db_name) as session:
            result = session.run("""
                MATCH (n)
                WHERE n.query IS NOT NULL
                RETURN n.query AS query,
                       min(n.created_at) AS created_at
                ORDER BY created_at DESC
                """)

            history = []
            for record in result:
                history.append(
                    {"query": record["query"], "created_at": record["created_at"]}
                )

            return {"history": history}

    except ServiceUnavailable as e:
        raise ConnectionError(f"Neo4j сервер недоступен: {e}") from e
    except AuthError as e:
        raise PermissionError(f"Ошибка авторизации: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Ошибка при получении истории: {e}") from e


def update_node(driver, db_name, query, node_uid, new_properties=None, new_labels=None):

    if not query or not query.strip():
        raise ValueError("query не может быть пустым")
    if not node_uid or not node_uid.strip():
        raise ValueError("node_uid не может быть пустым")
    if new_properties is None and new_labels is None:
        raise ValueError("Необходимо передать new_properties или new_labels")

    PROTECTED = {"uid", "query", "source_uid"}

    def _execute(tx):
        check = tx.run(
            "MATCH (n {uid: $uid, query: $q}) RETURN labels(n) AS lbls",
            uid=node_uid,
            q=query,
        )
        record = check.single()
        if not record:
            raise ValueError(f"Узел с uid='{node_uid}' не найден в графе '{query}'")

        if new_properties is not None:
            safe_props = {k: v for k, v in new_properties.items() if k not in PROTECTED}
            props_to_set = {k: v for k, v in safe_props.items() if v is not None}
            props_to_remove = [k for k, v in safe_props.items() if v is None]

            if props_to_set:
                tx.run(
                    "MATCH (n {uid: $uid, query: $q}) SET n += $props",
                    uid=node_uid,
                    q=query,
                    props=props_to_set,
                )

            for prop_key in props_to_remove:
                tx.run(
                    """
                    MATCH (n {uid: $uid, query: $q})
                    SET n = apoc.map.removeKey(properties(n), $key)
                    SET n.uid = $uid, n.query = $q
                    """,
                    uid=node_uid,
                    q=query,
                    key=prop_key,
                )

        if new_labels is not None:
            if not new_labels:
                raise ValueError("new_labels не может быть пустым списком")

            current_labels = record["lbls"]
            labels_to_remove = [lb for lb in current_labels if lb not in new_labels]
            labels_to_add = [lb for lb in new_labels if lb not in current_labels]

            if labels_to_remove:
                remove_clause = ":".join(labels_to_remove)
                tx.run(
                    f"MATCH (n {{uid: $uid, query: $q}}) REMOVE n:{remove_clause}",
                    uid=node_uid,
                    q=query,
                )

            if labels_to_add:
                add_clause = ":".join(labels_to_add)
                tx.run(
                    f"MATCH (n {{uid: $uid, query: $q}}) SET n:{add_clause}",
                    uid=node_uid,
                    q=query,
                )

    try:
        with driver.session(database=db_name) as session:
            session.execute_write(_execute)
    except (ServiceUnavailable, SessionExpired, TransientError) as e:
        raise ConnectionError(f"Neo4j не доступен при обновлении узла: {e}") from e
    except AuthError as e:
        raise PermissionError(f"Ошибка авторизации при обновлении узла: {e}") from e
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Ошибка при обновлении узла '{node_uid}': {e}") from e
