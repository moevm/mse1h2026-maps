# mse-template

## Требования

### Для запуска через Docker

- **Docker** 28 или выше
- **Git**

## Установка и запуск

### Запуск через Docker

1. **Клонируйте репозиторий**

```bash
git clone https://github.com/moevm/mse1h2026-maps.git
cd mse1h2026-maps
```

2. **Настройте переменные окружения**

Скопируйте **.env.example** в **.env** и при необходимости отредактируйте.

```bash
cp .env.example .env
```

Для Windows:

```cmd
copy .env.example .env
```

3. **Выберите вариант запуска**

#### Dev-версия

Используется для разработки.

В dev-версии:
- код проекта подключается в контейнер через volume;
- после изменения кода обычно не нужно пересобирать контейнер;
- наружу открыты дополнительные порты PostgreSQL, Neo4j и Redis.

```bash
docker compose -f docker-compose.dev.yml up --build
```

Миграции:

```bash
docker compose -f docker-compose.dev.yml exec server python src/django/maps/manage.py migrate
```

Приложение станет доступно по адресу:

```text
http://localhost:8000
```

Дополнительные dev-порты:

```text
PostgreSQL:    localhost:15432
Redis:         localhost:16379
Neo4j Browser: http://localhost:17474
Neo4j Bolt:    bolt://localhost:17687
```

#### Prod-версия

Используется для production-like запуска.

В prod-версии:
- код не подключается с диска;
- приложение использует код из собранного Docker image;
- наружу открыт только порт приложения.

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Миграции:

```bash
docker compose -f docker-compose.prod.yml exec server python src/django/maps/manage.py migrate
```

Приложение станет доступно по адресу:

```text
http://localhost:8000
```

## Остановка

Dev:

```bash
docker compose -f docker-compose.dev.yml down
```

Prod:

```bash
docker compose -f docker-compose.prod.yml down
```

## Проверка работоспособности

Инструкции по проверке работоспособности проекта (основной функциональности и результатов).

## Дополнительная информация

Любая информация, которую команда посчитает нужной разместить.
