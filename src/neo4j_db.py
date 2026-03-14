def clear_database(driver):
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

def create_nodes(tx, nodes):
    for node in nodes:
        labels = ':'.join(node['labels'])
        tx.run(
            f"MERGE (n:{labels} {{uid: $uid}}) SET n += $props",
            uid=node['uid'],
            props=node.get('properties', {}),
        )

def create_relationships(tx, relationships):
    for rel in relationships:
        tx.run(
            f"""
            MATCH (a {{uid: $from_uid}})
            MATCH (b {{uid: $to_uid}})
            MERGE (a)-[r:{rel['type']}]->(b)
            SET r += $props
            """,
            from_uid=rel['from_uid'],
            to_uid=rel['to_uid'],
            props=rel.get('properties', {}),
        )


def set_to_neo4j(driver, data):
    with driver.session() as session:
        session.execute_write(create_nodes, data['nodes'])
        session.execute_write(create_relationships, data['relationships'])

# def get_from_neo4j(driver):
#     """Получить граф"""
#     pass
