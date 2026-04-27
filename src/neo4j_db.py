import re
import time
import logging
from neo4j_viz.neo4j import from_neo4j
from neo4j.exceptions import ServiceUnavailable, AuthError, ClientError, TransientError, ConstraintError

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
                f"SET PASSWORD '{neo4j_password}' CHANGE NOT REQUIRED"
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
            session.run(f"GRANT CREATE NEW NODE LABEL ON DATABASE {db_name} TO {role_name}")
            session.run(f"GRANT CREATE NEW RELATIONSHIP TYPE ON DATABASE {db_name} TO {role_name}")
            session.run(f"GRANT CREATE NEW PROPERTY NAME ON DATABASE {db_name} TO {role_name}")

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

    if not nodes:
        raise ValueError("nodes не может быть пустым")

    uid_map = {}
    query = query.strip().lower()

    for node in nodes:
        try:
            if "uid" not in node:
                raise ValueError(f"Узел не содержит обязательное поле uid: {node}")
            if "labels" not in node or not node["labels"]:
                raise ValueError(f"Узел не содержит обязательное поле labels: {node}")

            labels = ":".join(node["labels"])
            props = node.get("properties", {})
            old_uid = node["uid"]

            label_en = props.get("label_en", "")
            semantic_part = normalize_name(label_en) if label_en else "no_label"

            props["source_uid"] = old_uid
            props["query"] = query
            new_uid = f"{old_uid}::{semantic_part}"

            uid_map[old_uid] = new_uid
            tx.run(
                f"MERGE (n:{labels} {{uid: $uid, query: $query_param}}) SET n += $props",
                uid=new_uid,
                query_param=query,
                props=props,
            )

        except ServiceUnavailable as e:
            raise ConnectionError(f"Neo4j сервер недоступен при создании узла {node.get('uid', '?')}: {e}") from e
        except AuthError as e:
            raise PermissionError(f"Ошибка авторизации при создании узла {node.get('uid', '?')}: {e}") from e
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Не удалось создать узел {node.get('uid', '?')}: {e}") from e

    return uid_map


def create_relationships(tx, relationships, uid_map, query):
    if not isinstance(relationships, list):
        raise ValueError("relationships должен быть списком")

    query = query.strip().lower()

    for rel in relationships:
        try:
            if "from_uid" not in rel or "to_uid" not in rel:
                raise ValueError(f"Связь не содержит from_uid или to_uid: {rel}")
            if "type" not in rel:
                raise ValueError(f"Связь не содержит обязательное поле type: {rel}")

            from_uid = uid_map.get(rel["from_uid"], rel["from_uid"])
            to_uid = uid_map.get(rel["to_uid"], rel["to_uid"])

            if from_uid == to_uid:
                continue

            clean_type = clean_rel_type(rel["type"])
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
                props=rel.get("properties", {}),
            )

        except ValueError:
            raise

        except ServiceUnavailable as e:
            raise ConnectionError(f"Neo4j сервер недоступен при создании связи: {e}") from e

        except AuthError as e:
            raise PermissionError(f"Ошибка авторизации при создании связи: {e}") from e

        except ClientError as e:
            if "node not found" in str(e).lower():
                raise ValueError(
                    f"Узел не найден для связи: {rel.get('from_uid', '?')} → {rel.get('to_uid', '?')}. Ошибка: {e}") from e
            else:
                raise ValueError(f"Ошибка клиента Neo4j при создании связи: {e}") from e

        except TransientError as e:
            raise TimeoutError(f"Временная ошибка Neo4j при создании связи, попробуйте позже: {e}") from e

        except Exception as e:
            raise RuntimeError(
                f"Ошибка при создании связи {rel.get('from_uid', '?')} → {rel.get('to_uid', '?')}: {e}") from e


def set_to_neo4j(driver, data):

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

    query = data["query"]

    def _execute(tx, data):
        uid_map = create_nodes(tx, data["nodes"], query)
        create_relationships(tx, data["relationships"], uid_map, query)

    try:
        with driver.session() as session:
            session.execute_write(_execute, data)

    except ServiceUnavailable as e:
        raise ConnectionError(f"Neo4j не доступен при записи графа '{query}': {e}") from e

    except AuthError as e:
        raise PermissionError(f"Ошибка авторизации при записи графа '{query}': {e}") from e

    except ConstraintError as e:
        raise ValueError(f"Нарушение уникальности при записи графа '{query}': {e}") from e

    except Exception as e:
        raise RuntimeError(f"Ошибка при записи графа '{query}': {e}") from e

def get_from_neo4j(driver, query):

    if not query or not query.strip():
        raise ValueError("query не может быть пустым")

    query = query.strip().lower()

    try:
        with driver.session() as session:
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
                nodes.append({
                    "id": node.id,
                    "caption": node.caption,
                    "labels": node.properties.get("labels", []),
                    "properties": node.properties,
                })

            relationships = []
            for rel in VG.relationships:
                relationships.append({
                    "id": rel.id,
                    "from": rel.source,
                    "to": rel.target,
                    "caption": rel.properties.get("type", ""),
                    "properties": rel.properties,
                })

            return nodes, relationships

    except ServiceUnavailable as e:
        raise ConnectionError(f"Neo4j не доступен: {e}") from e

    except AuthError as e:
        raise PermissionError(f"Ошибка авторизации: {e}") from e

    except AttributeError as e:
        raise ValueError(f"Отсутствует поле в данных: {e}") from e

    except Exception as e:
        raise RuntimeError(f"Ошибка: {e}") from e