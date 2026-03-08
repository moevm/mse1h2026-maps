# 1. Отправление запроса к парсеру
def celery_parser_reqest(topic: str) -> None:
    # TODO: флаги о том, какие источники worker должен отработать
    pass


# 2. Получение данных из Neo4j, пока что конкретная логика не определена
# поэтому аргументы и выход не определены
def recive_data_neo4j():
    pass


# 3. Размещение данных в SQL
def put_SQL_data(JSON_path) -> None:
    pass


# 4. Получение данных из SQL базы данных
def get_SQL_data(id):
    # Получает данные из SQL на выходе JSON
    pass