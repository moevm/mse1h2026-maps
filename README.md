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

### Переменные окружения

Пользователь может вручную настроить следующие переменные в файле **.env**:

| Переменная | Описание | Пример |
|---|---|---|
| `DJANGO_SECRET` | Секретный ключ Django. Для production нужно заменить на свой. | `django-insecure-local-dev-only` |
| `DJANGO_DEBUG` | Режим отладки Django. Для разработки — `1`, для production — `0`. | `1` |
| `DJANGO_ALLOWED_HOSTS` | Список разрешённых хостов через запятую. | `localhost,127.0.0.1,0.0.0.0,server` |
| `DB_NAME` | Название базы данных PostgreSQL. | `mapsdb` |
| `DB_USER` | Пользователь PostgreSQL. | `admin` |
| `DB_PASSWORD` | Пароль пользователя PostgreSQL. | `CHANGETHAT` |
| `DB_HOST` | Хост PostgreSQL для локального запуска без Docker. В Docker Compose переопределяется на `postgres`. | `localhost` |
| `DB_PORT` | Порт PostgreSQL для локального запуска без Docker. | `5432` |
| `NEO_URI` | URI подключения к Neo4j для локального запуска без Docker. В Docker Compose переопределяется на `bolt://neo4j:7687`. | `bolt://localhost:7687` |
| `NEO_USER` | Пользователь Neo4j. | `neo4j` |
| `NEO_PASSWORD` | Пароль пользователя Neo4j. | `12345678` |
| `NEO4J_ACCEPT_LICENSE_AGREEMENT` | Подтверждение лицензии Neo4j Enterprise. | `yes` |
| `CELERY_BROKER_URL` | URL брокера Celery для локального запуска без Docker. В Docker Compose переопределяется на `redis://redis:6379/0`. | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | URL backend-хранилища результатов Celery для локального запуска без Docker. В Docker Compose переопределяется на `redis://redis:6379/0`. | `redis://localhost:6379/0` |

В Docker Compose сервисы обращаются друг к другу по именам контейнеров:

```text
postgres:5432
neo4j:7687
redis:6379
```

Поэтому значения `DB_HOST`, `NEO_URI`, `CELERY_BROKER_URL` и `CELERY_RESULT_BACKEND` из `.env` могут использоваться для локального запуска, а внутри Docker переопределяются compose-файлами.

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
