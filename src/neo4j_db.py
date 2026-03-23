from neo4j_viz.neo4j import from_neo4j
import re

def normalize_name(name):
    words = name.lower().strip().split()
    words = sorted(words)
    words = [re.sub(r"[^a-z0-9]", "", w) for w in words]
    return "_".join(words)

def clean_rel_type(rel_type):
    rel_type = re.sub(r'\([^)]*\)$', '', rel_type)
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '_', rel_type)
    cleaned = re.sub(r'_+', '_', cleaned)
    cleaned = cleaned.strip('_')
    return cleaned


def create_nodes(tx, nodes, query_name):
    uid_map = {}
    for node in nodes:
        labels = ':'.join(node['labels'])
        props = node.get('properties', {})
        old_uid = node['uid']

        if 'label_en' in props:
            new_uid = f"{normalize_name(props['label_en'])}"
        else:
            new_uid = old_uid
        props['query'] = query_name

        uid_map[old_uid] = new_uid
        tx.run(
            f"MERGE (n:{labels} {{uid: $uid, query: $query_param}}) SET n += $props",
            uid=new_uid,
            query_param=query_name,
            props=props,
        )
    return uid_map


def create_relationships(tx, relationships, uid_map, query):
    for rel in relationships:
        from_uid = uid_map.get(rel['from_uid'], rel['from_uid'])
        to_uid = uid_map.get(rel['to_uid'], rel['to_uid'])
        clean_type = clean_rel_type(rel['type'])

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
            props=rel.get('properties', {}),
        )

def set_to_neo4j(driver, data):
    query = data['query']
    def _execute(tx, data):
        uid_map = create_nodes(tx, data['nodes'], query)
        create_relationships(tx, data['relationships'], uid_map, query)

    with driver.session() as session:
        session.execute_write(_execute, data)

def get_from_neo4j(driver, query):
    with driver.session() as session:
        result = session.run("""
            MATCH (n)-[r]->(m)
            WHERE n.query = $q AND m.query = $q
            RETURN n, r, m
        """, {"q": query})

        vg = from_neo4j(result, row_limit=10000)
        return vg